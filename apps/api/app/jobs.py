"""Single worker, bounded admission, durable observable status; restart fails explicitly."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time
from uuid import uuid4
from sqlalchemy import select
from fastapi import HTTPException
from .database import JobRecord
from .ollama_session import GenerationError
from .architectural_generator import progress_callback


class JobManager:
    def __init__(self, repository):
        self.repository=repository
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='p2c-generation')
        self.lock=Lock();self.pending=0

    def initialize(self):
        with self.repository.sessions() as db:
            for job in db.scalars(select(JobRecord)):
                if job.data['status'] in {'queued','running'}:
                    job.data={**job.data,'status':'failed','stage':'interrupted',
                              'error':'Servidor reiniciado durante a geração. Envie novamente; nenhum resultado foi declarado pronto.',
                              'updatedAt':time.time()}
            db.commit()

    def get(self,job_id):
        with self.repository.sessions() as db:
            job=db.get(JobRecord,job_id)
            if job is None: raise HTTPException(404,'Geração não encontrada.')
            return job.data

    def update(self,job_id,**changes):
        with self.repository.sessions() as db:
            job=db.get(JobRecord,job_id)
            job.data={**job.data,**changes,'updatedAt':time.time()}
            db.commit()

    def submit(self,work):
        with self.lock:
            if self.pending>=4:
                raise HTTPException(429,'Fila cheia. Aguarde uma geração terminar.')
            ident=uuid4().hex
            data={'id':ident,'status':'queued','stage':'received','createdAt':time.time(),
                  'updatedAt':time.time(),'events':[{'stage':'received','at':time.time()}]}
            with self.repository.sessions() as db:
                rows=list(db.scalars(select(JobRecord)))
                terminal=sorted((r for r in rows if r.data['status'] in {'ready','failed'}),key=lambda r:r.data['createdAt'])
                for old in terminal[:max(0,len(rows)-199)]: db.delete(old)
                db.add(JobRecord(id=ident,data=data));db.commit()
            self.pending+=1
            self.executor.submit(self.run,ident,work)
            return data

    def run(self,ident,work):
        def report(stage):
            current=self.get(ident)
            self.update(ident,stage=stage,events=current['events']+[{'stage':stage,'at':time.time()}])
        token=progress_callback.set(report)
        try:
            self.update(ident,status='running')
            result=work()
            report('ready_for_review' if result['status']=='pending' else 'ready_for_minecraft')
            self.update(ident,status='ready',buildId=result['id'])
        except (GenerationError,HTTPException) as exc:
            self.update(ident,status='failed',error=str(exc) if isinstance(exc,GenerationError) else exc.detail,
                        httpStatus=exc.status_code)
        except Exception:
            import logging
            logging.getLogger('photo2craft').exception('Falha no job %s',ident)
            self.update(ident,status='failed',error='Falha interna ao gerar. Consulte o log pelo ID da geração.',httpStatus=500)
        finally:
            progress_callback.reset(token)
            with self.lock: self.pending-=1

    def close(self):
        self.executor.shutdown(wait=True)
