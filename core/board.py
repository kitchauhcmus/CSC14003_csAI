import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping
from core.constants import Orientation, SwitchBehavior, TileType
from core.state import State, is_strict_int, strict_int

# Bảng ký hiệu ASCII hỗ trợ viết level nhanh (chỉ dùng '#' cho VOID để tránh lỗi cắt dấu cách cuối dòng)
ASCII_TO_TILE: dict[str, TileType] = {
    "#": TileType.VOID,
    ".": TileType.FLOOR,
    "S": TileType.FLOOR,       # Ô xuất phát (trên nền sàn thường)
    "G": TileType.GOAL,
    "F": TileType.FRAGILE,
    "o": TileType.SOFT_SWITCH,
    "x": TileType.HEAVY_SWITCH,
    "(": TileType.SPLIT_SWITCH,
    "B": TileType.BRIDGE,
}


def _parse_coord(pair: Any, context: str) -> tuple[int, int]:
    """Đọc và chuẩn hóa tọa độ (r, c) về tuple[int, int] với kiểm tra kiểu int nghiêm ngặt."""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ValueError(f"{context} must be a (r, c) pair, got {pair!r}.")
    return strict_int(pair[0], f"{context}[0]"), strict_int(pair[1], f"{context}[1]")


@dataclass(frozen=True, slots=True)
class SwitchSpec:
    """Thông số kỹ thuật của một công tắc điều khiển cầu (Soft hoặc Heavy)."""
    behavior: SwitchBehavior
    targets: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if not isinstance(self.behavior, SwitchBehavior):
            raise ValueError(f"Invalid SwitchBehavior: {self.behavior!r}")
        if not isinstance(self.targets, (tuple, list)) or not self.targets:
            raise ValueError("SwitchSpec.targets must be a non-empty tuple or list of (r, c) pairs.")
        normalized = tuple(
            _parse_coord(t, f"SwitchSpec.targets[{i}]") for i, t in enumerate(self.targets)
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"Duplicate target bridges in SwitchSpec: {normalized}")
        object.__setattr__(self, "targets", normalized)


@dataclass(frozen=True, slots=True)
class SplitSpec:
    """Thông số của công tắc phân thân (Split Switch): tọa độ 2 ô xuất hiện của 2 khối 1x1x1."""
    spawn_positions: tuple[tuple[int, int], tuple[int, int]]

    def __post_init__(self):
        if not isinstance(self.spawn_positions, (tuple, list)) or len(self.spawn_positions) != 2:
            raise ValueError("SplitSpec.spawn_positions must contain exactly 2 (r, c) pairs.")
        p1 = _parse_coord(self.spawn_positions[0], "SplitSpec.spawn_positions[0]")
        p2 = _parse_coord(self.spawn_positions[1], "SplitSpec.spawn_positions[1]")
        if abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) < 2:
            raise ValueError(
                f"Split spawn positions {p1}, {p2} cannot be identical or adjacent."
            )
        object.__setattr__(self, "spawn_positions", (p1, p2))


class Board:
    """
    Lưu trữ dữ liệu tĩnh bất biến của một màn chơi (Stage).
    Hỗ trợ đầy đủ pickle để chạy benchmark đa tiến trình (multiprocessing).
    """

    __slots__ = (
        "grid", "rows", "cols", "start_pos", "goal_pos", "initial_bridges",
        "switches", "split_switches", "name", "lint_warnings", "_frozen",
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError("Board is immutable; create a new Board for another level.")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Board is immutable.")

    def __init__(
        self,
        grid: Iterable[Iterable[TileType]],
        start_pos: tuple[int, int],
        goal_pos: tuple[int, int] | None = None,
        initial_bridges: Iterable[tuple[int, int]] = (),
        switches: Mapping[tuple[int, int], SwitchSpec] | None = None,
        split_switches: Mapping[tuple[int, int], SplitSpec] | None = None,
        name: str = "Unnamed Stage",
    ):
        try:
            self.grid: tuple[tuple[TileType, ...], ...] = tuple(tuple(row) for row in grid)
        except TypeError as exc:
            raise ValueError("Grid must be a 2D iterable of TileType.") from exc

        if not self.grid or not self.grid[0]:
            raise ValueError("Grid cannot be empty.")

        self.rows: int = len(self.grid)
        self.cols: int = len(self.grid[0])
        for r, row in enumerate(self.grid):
            if len(row) != self.cols:
                raise ValueError(
                    f"Row {r} has length {len(row)}, expected {self.cols} to match row 0."
                )
            for c, cell in enumerate(row):
                if not isinstance(cell, TileType):
                    raise ValueError(f"Grid cell at ({r}, {c}) is not a TileType: {cell!r}")

        self.start_pos: tuple[int, int] = _parse_coord(start_pos, "start_pos")

        goals = [
            (r, c)
            for r, row in enumerate(self.grid)
            for c, t in enumerate(row)
            if t == TileType.GOAL
        ]
        if len(goals) != 1:
            raise ValueError(f"Grid must contain exactly one GOAL tile, found {len(goals)}: {goals}.")

        if goal_pos is None:
            self.goal_pos: tuple[int, int] = goals[0]
        else:
            parsed_goal = _parse_coord(goal_pos, "goal_pos")
            if parsed_goal != goals[0]:
                raise ValueError(
                    f"goal_pos {parsed_goal} does not match the GOAL tile on grid at {goals[0]}."
                )
            self.goal_pos = parsed_goal

        self.initial_bridges: frozenset[tuple[int, int]] = frozenset(
            _parse_coord(p, "initial_bridges item") for p in initial_bridges
        )

        norm_switches: dict[tuple[int, int], SwitchSpec] = {}
        if switches:
            for k, v in switches.items():
                pos_k = _parse_coord(k, "switches key")
                if not isinstance(v, SwitchSpec):
                    raise ValueError(f"Invalid SwitchSpec at {pos_k}: {v!r}")
                norm_switches[pos_k] = v

        norm_splits: dict[tuple[int, int], SplitSpec] = {}
        if split_switches:
            for k, v in split_switches.items():
                pos_k = _parse_coord(k, "split_switches key")
                if not isinstance(v, SplitSpec):
                    raise ValueError(f"Invalid SplitSpec at {pos_k}: {v!r}")
                norm_splits[pos_k] = v

        self.switches: Mapping[tuple[int, int], SwitchSpec] = MappingProxyType(norm_switches)
        self.split_switches: Mapping[tuple[int, int], SplitSpec] = MappingProxyType(norm_splits)
        self.name: str = str(name)
        self.lint_warnings: tuple[str, ...] = ()

        self._validate_board()
        object.__setattr__(self, "_frozen", True)

    def __getstate__(self) -> dict[str, Any]:
        """Chuyển MappingProxyType về dict thường khi pickle (hỗ trợ multiprocessing)."""
        state = {name: getattr(self, name) for name in self.__slots__ if name != "_frozen"}
        state["switches"] = dict(self.switches)
        state["split_switches"] = dict(self.split_switches)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Khôi phục lại MappingProxyType sau khi unpickle."""
        for name, value in state.items():
            if name in ("switches", "split_switches"):
                value = MappingProxyType(dict(value))
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_frozen", True)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return NotImplemented
        return (
            self.name == other.name
            and self.grid == other.grid
            and self.start_pos == other.start_pos
            and self.goal_pos == other.goal_pos
            and self.initial_bridges == other.initial_bridges
            and dict(self.switches) == dict(other.switches)
            and dict(self.split_switches) == dict(other.split_switches)
        )

    def __hash__(self) -> int:
        """
        Cho phép dùng Board làm key trong dict / set / functools.lru_cache (VD: cache bảng khoảng cách A*).
        Không cache kết quả vào attribute để an toàn tuyệt đối khi pickle qua các process có PYTHONHASHSEED khác nhau.
        """
        return hash(
            (
                self.name,
                self.grid,
                self.start_pos,
                self.goal_pos,
                self.initial_bridges,
                frozenset(self.switches.items()),
                frozenset(self.split_switches.items()),
            )
        )

    def _validate_board(self) -> None:
        """Kiểm tra chặt chẽ tính toàn vẹn của bản đồ ngay khi khởi tạo."""
        if not self.in_bounds(*self.start_pos):
            raise ValueError(f"Start position {self.start_pos} is out of bounds.")
        start_tile = self.tile_at(*self.start_pos)
        forbidden_start = (
            TileType.VOID,
            TileType.FRAGILE,
            TileType.GOAL,
            TileType.SOFT_SWITCH,
            TileType.HEAVY_SWITCH,
            TileType.SPLIT_SWITCH,
        )
        if start_tile in forbidden_start or (
            start_tile == TileType.BRIDGE and self.start_pos not in self.initial_bridges
        ):
            raise ValueError(
                f"Start tile {start_tile.name} at {self.start_pos} is not allowed."
            )

        for br in self.initial_bridges:
            if self.tile_at(*br) != TileType.BRIDGE:
                raise ValueError(f"Initial bridge at {br} is not a TileType.BRIDGE.")

        openable_bridges: set[tuple[int, int]] = set()
        for pos, spec in self.switches.items():
            tile = self.tile_at(*pos)
            if tile not in (TileType.SOFT_SWITCH, TileType.HEAVY_SWITCH):
                raise ValueError(f"Switch at {pos} does not match grid tile {tile}.")
            for br in spec.targets:
                if self.tile_at(*br) != TileType.BRIDGE:
                    raise ValueError(f"Switch target {br} is not a TileType.BRIDGE.")
                if spec.behavior != SwitchBehavior.PERMANENT_CLOSE:
                    openable_bridges.add(br)

        for pos, split_spec in self.split_switches.items():
            if self.tile_at(*pos) != TileType.SPLIT_SWITCH:
                raise ValueError(f"Split switch at {pos} does not match grid tile.")
            for sp in split_spec.spawn_positions:
                if not self.in_bounds(*sp) or self.tile_at(*sp) == TileType.VOID:
                    raise ValueError(f"Invalid split spawn position {sp} for switch at {pos}.")
                

        dead_bridges: list[tuple[int, int]] = []
        risky_notes: list[str] = []
        for r, row in enumerate(self.grid):
            for c, tile in enumerate(row):
                if tile in (TileType.SOFT_SWITCH, TileType.HEAVY_SWITCH):
                    if (r, c) not in self.switches:
                        raise ValueError(f"{tile.name} at ({r}, {c}) is missing its SwitchSpec.")
                elif tile == TileType.SPLIT_SWITCH:
                    if (r, c) not in self.split_switches:
                        raise ValueError(f"SPLIT_SWITCH at ({r}, {c}) is missing its SplitSpec.")
                    # Lint mềm: spawn rơi trên cầu đóng sẵn nhưng CÓ switch mở được.
                    # Nước đi chỉ khả thi nếu người chơi đã mở cầu từ trước.
                    for sp in self.split_switches[(r, c)].spawn_positions:
                        if (
                            self.tile_at(*sp) == TileType.BRIDGE
                            and sp not in self.initial_bridges
                            and sp in openable_bridges
                        ):
                            risky_notes.append(
                                f"[{self.name}] Split switch at ({r}, {c}) spawns a cube on bridge {sp} "
                                f"that is closed initially; only possible if a switch opened it beforehand."
                            )
                elif tile == TileType.BRIDGE:
                    if (r, c) not in self.initial_bridges and (r, c) not in openable_bridges:
                        dead_bridges.append((r, c))

        hard_warnings: list[str] = []
        if dead_bridges:
            msg = (
                f"[{self.name}] Permanently impassable bridge tile(s) at {dead_bridges}: "
                f"closed initially and not targeted by any opening switch."
            )
            hard_warnings.append(msg)
            warnings.warn(msg, UserWarning)

        # risky_notes chỉ lưu để tham khảo, KHÔNG warnings.warn (tránh báo oan)
        self.lint_warnings = tuple(hard_warnings) + tuple(risky_notes)

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def tile_at(self, r: int, c: int) -> TileType:
        """Đường nóng (hot path): inline kiểm tra biên để tránh chi phí gọi hàm phụ."""
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.grid[r][c]
        return TileType.VOID

    def initial_state(self) -> State:
        """Trả về trạng thái bắt đầu của màn chơi."""
        return State(
            positions=(self.start_pos,),
            orientation=Orientation.STANDING,
            active_bridges=self.initial_bridges,
        )

    def to_dict(self) -> dict[str, Any]:
        """Xuất Board ra dictionary chuẩn JSON."""
        return {
            "name": self.name,
            "start_pos": list(self.start_pos),
            "goal_pos": list(self.goal_pos),
            "grid": [[tile.name for tile in row] for row in self.grid],
            "initial_bridges": [list(p) for p in sorted(self.initial_bridges)],
            "switches": [
                {
                    "pos": list(pos),
                    "behavior": spec.behavior.name,
                    "targets": [list(t) for t in spec.targets],
                }
                for pos, spec in sorted(self.switches.items())
            ],
            "split_switches": [
                {
                    "pos": list(pos),
                    "spawn_positions": [list(sp) for sp in spec.spawn_positions],
                }
                for pos, spec in sorted(self.split_switches.items())
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], default_name: str = "Unnamed Stage") -> "Board":
        """
        Tạo Board từ dictionary.
        Hỗ trợ grid dạng mảng 2D (tên Enum hoặc số nguyên) HOẶC mảng các chuỗi ASCII.
        """
        if not isinstance(data, Mapping):
            raise ValueError("Stage data must be a mapping/dictionary.")

        stage_name = str(data.get("name", default_name))
        if "grid" not in data:
            raise ValueError(f"[{stage_name}] Missing required field 'grid'.")

        raw_grid = data["grid"]
        if not isinstance(raw_grid, (list, tuple)) or not raw_grid:
            raise ValueError(f"[{stage_name}] 'grid' must be a non-empty list of rows.")

        parsed_grid: list[list[TileType]] = []
        ascii_starts: list[tuple[int, int]] = []

        for r, row in enumerate(raw_grid):
            parsed_row: list[TileType] = []
            if isinstance(row, str):
                for c, ch in enumerate(row):
                    if ch not in ASCII_TO_TILE:
                        raise ValueError(
                            f"[{stage_name}] Unknown ASCII tile {ch!r} at (row={r}, col={c})."
                        )
                    if ch == "S":
                        ascii_starts.append((r, c))
                    parsed_row.append(ASCII_TO_TILE[ch])
            elif isinstance(row, (list, tuple)):
                for c, cell in enumerate(row):
                    if isinstance(cell, str):
                        if cell in TileType.__members__:
                            tile = TileType[cell]
                        elif len(cell) == 1 and cell in ASCII_TO_TILE:
                            if cell == "S":
                                ascii_starts.append((r, c))
                            tile = ASCII_TO_TILE[cell]
                        else:
                            raise ValueError(
                                f"[{stage_name}] Invalid tile string {cell!r} at (row={r}, col={c})."
                            )
                    elif is_strict_int(cell):
                        try:
                            tile = TileType(cell)
                        except ValueError as exc:
                            raise ValueError(
                                f"[{stage_name}] Invalid tile integer {cell!r} at (row={r}, col={c})."
                            ) from exc
                    else:
                        raise ValueError(
                            f"[{stage_name}] Invalid tile {cell!r} at (row={r}, col={c})."
                        )
                    parsed_row.append(tile)
            else:
                raise ValueError(f"[{stage_name}] Row {r} in 'grid' must be a list or string.")
            parsed_grid.append(parsed_row)

        if len(ascii_starts) > 1:
            raise ValueError(f"[{stage_name}] Multiple 'S' start markers in grid: {ascii_starts}.")
        if "start_pos" in data and data["start_pos"] is not None:
            start_pos = _parse_coord(data["start_pos"], f"[{stage_name}] start_pos")
            if ascii_starts and ascii_starts[0] != start_pos:
                raise ValueError(
                    f"[{stage_name}] start_pos {start_pos} conflicts with 'S' marker at {ascii_starts[0]}."
                )
        elif ascii_starts:
            start_pos = ascii_starts[0]
        else:
            raise ValueError(f"[{stage_name}] Missing 'start_pos' (and no 'S' marker in grid).")

        goal_pos: tuple[int, int] | None = None
        if "goal_pos" in data and data["goal_pos"] is not None:
            goal_pos = _parse_coord(data["goal_pos"], f"[{stage_name}] goal_pos")

        raw_init_bridges = data.get("initial_bridges", [])
        if not isinstance(raw_init_bridges, (list, tuple)):
            raise ValueError(f"[{stage_name}] 'initial_bridges' must be a list of [r, c] pairs.")
        initial_bridges = [
            _parse_coord(p, f"[{stage_name}] initial_bridges[{i}]")
            for i, p in enumerate(raw_init_bridges)
        ]

        switches: dict[tuple[int, int], SwitchSpec] = {}
        raw_switches = data.get("switches", [])
        if not isinstance(raw_switches, (list, tuple)):
            raise ValueError(f"[{stage_name}] 'switches' must be a list.")
        for idx, item in enumerate(raw_switches):
            if not isinstance(item, Mapping):
                raise ValueError(f"[{stage_name}] switches[{idx}] must be a dict.")
            if "pos" not in item or "behavior" not in item or "targets" not in item:
                raise ValueError(
                    f"[{stage_name}] switches[{idx}] must contain 'pos', 'behavior', and 'targets'."
                )
            pos = _parse_coord(item["pos"], f"[{stage_name}] switches[{idx}].pos")
            if pos in switches:
                raise ValueError(f"[{stage_name}] Duplicate switch definition at {pos}.")

            raw_beh = item["behavior"]
            if isinstance(raw_beh, str):
                try:
                    behavior = SwitchBehavior[raw_beh]
                except KeyError as exc:
                    raise ValueError(
                        f"[{stage_name}] Invalid switch behavior {raw_beh!r} at {pos}."
                    ) from exc
            elif is_strict_int(raw_beh):
                try:
                    behavior = SwitchBehavior(raw_beh)
                except ValueError as exc:
                    raise ValueError(
                        f"[{stage_name}] Invalid switch behavior {raw_beh!r} at {pos}."
                    ) from exc
            else:
                raise ValueError(f"[{stage_name}] Invalid switch behavior {raw_beh!r} at {pos}.")

            try:
                switches[pos] = SwitchSpec(behavior=behavior, targets=item["targets"])
            except ValueError as exc:
                raise ValueError(f"[{stage_name}] At switch {pos}: {exc}") from exc

        split_switches: dict[tuple[int, int], SplitSpec] = {}
        raw_splits = data.get("split_switches", [])
        if not isinstance(raw_splits, (list, tuple)):
            raise ValueError(f"[{stage_name}] 'split_switches' must be a list.")
        for idx, item in enumerate(raw_splits):
            if not isinstance(item, Mapping):
                raise ValueError(f"[{stage_name}] split_switches[{idx}] must be a dict.")
            if "pos" not in item or "spawn_positions" not in item:
                raise ValueError(
                    f"[{stage_name}] split_switches[{idx}] must contain 'pos' and 'spawn_positions'."
                )
            pos = _parse_coord(item["pos"], f"[{stage_name}] split_switches[{idx}].pos")
            if pos in split_switches:
                raise ValueError(f"[{stage_name}] Duplicate split_switch definition at {pos}.")

            try:
                split_switches[pos] = SplitSpec(spawn_positions=item["spawn_positions"])
            except ValueError as exc:
                raise ValueError(f"[{stage_name}] At split_switch {pos}: {exc}") from exc

        try:
            return cls(
                grid=parsed_grid,
                start_pos=start_pos,
                goal_pos=goal_pos,
                initial_bridges=initial_bridges,
                switches=switches,
                split_switches=split_switches,
                name=stage_name,
            )
        except ValueError as exc:
            raise ValueError(f"[{stage_name}] {exc}") from exc

    @classmethod
    def from_json(cls, path: str | Path) -> "Board":
        """Đọc màn chơi từ file JSON chuẩn của nhóm, báo lỗi kèm tên file."""
        file_path = Path(path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise ValueError(f"Failed to load JSON from '{file_path}': {exc}") from exc

        try:
            return cls.from_dict(data, default_name=file_path.stem)
        except ValueError as exc:
            raise ValueError(f"In file '{file_path.name}': {exc}") from exc
