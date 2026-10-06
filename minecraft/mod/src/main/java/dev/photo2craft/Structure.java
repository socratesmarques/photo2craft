package dev.photo2craft;

import java.util.List;
import java.util.Map;

public record Structure(String id, String name, int width, int height, int depth, List<Cell> blocks) {
    public record Cell(int x, int y, int z, String block, Map<String, String> states) {}
    public int[] rotate(Cell cell, int turns) {
        return switch (Math.floorMod(turns, 4)) {
            case 1 -> new int[]{depth - 1 - cell.z(), cell.y(), cell.x()};
            case 2 -> new int[]{width - 1 - cell.x(), cell.y(), depth - 1 - cell.z()};
            case 3 -> new int[]{cell.z(), cell.y(), width - 1 - cell.x()};
            default -> new int[]{cell.x(), cell.y(), cell.z()};
        };
    }
}
