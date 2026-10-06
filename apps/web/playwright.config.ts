import { defineConfig } from '@playwright/test';
import path from 'node:path';
export default defineConfig({
  testDir: './e2e', timeout: 45000,
  use: { baseURL:'http://127.0.0.1:5173',viewport:{width:1440,height:1000},
    launchOptions: {executablePath:process.env.CHROMIUM_EXECUTABLE || undefined,args:['--enable-unsafe-swiftshader']} },
  webServer:[
    {command:'python -m uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port 8000',url:'http://127.0.0.1:8000/api/health',env:{DATA_DIR:path.resolve('.e2e-data'),AI_PROVIDER:'disabled'},reuseExistingServer:false},
    {command:'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',url:'http://127.0.0.1:5173',reuseExistingServer:false}
  ]
});
