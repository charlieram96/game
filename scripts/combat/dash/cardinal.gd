class_name Cardinal
extends RefCounted
## The four board directions dashes travel along.
##
## Creatures don't walk in battle: every move is a dash straight along one of
## East / South / West / North, a whole number of cells. Input devices pick
## the direction from a drag, a stick or keys:
##   * the dominant axis of the drag wins;
##   * near a 45° tie the previously shown direction is kept (hysteresis), so
##     the aim never flickers between two lanes;
##   * with no previous direction, ties go to the horizontal axis.

const EAST := Vector2(1, 0)
const SOUTH := Vector2(0, 1)
const WEST := Vector2(-1, 0)
const NORTH := Vector2(0, -1)
## Index order used by InputCommand.dash_dir.
const DIRS: Array[Vector2] = [EAST, SOUTH, WEST, NORTH]

## How far past 45° a drag must lean before the aim switches lanes.
const HYSTERESIS := 0.18


static func from_index(index: int) -> Vector2:
	if index < 0 or index >= DIRS.size():
		return Vector2.ZERO
	return DIRS[index]


static func index_of(v: Vector2) -> int:
	return DIRS.find(snap(v))


## Picks the dash direction for a drag/stick vector. `previous` (an index or
## -1) is kept while the vector stays close to the diagonal between lanes.
static func pick(v: Vector2, previous: int = -1) -> int:
	if v.length_squared() < 1e-8:
		return previous
	var ax := absf(v.x)
	var ay := absf(v.y)
	var horizontal: bool
	if previous >= 0 and absf(ax - ay) <= HYSTERESIS * maxf(ax, ay):
		horizontal = previous == 0 or previous == 2
	else:
		horizontal = ax >= ay
	if horizontal:
		return 0 if v.x >= 0.0 else 2
	return 1 if v.y >= 0.0 else 3


## Snap any direction to its dominant cardinal (ties -> horizontal).
static func snap(v: Vector2) -> Vector2:
	if v.length_squared() < 1e-8:
		return SOUTH
	if absf(v.x) >= absf(v.y):
		return EAST if v.x >= 0.0 else WEST
	return SOUTH if v.y > 0.0 else NORTH


static func is_cardinal(v: Vector2) -> bool:
	return v == EAST or v == WEST or v == NORTH or v == SOUTH


static func name_of(v: Vector2) -> String:
	if v == EAST:
		return "E"
	if v == WEST:
		return "W"
	if v == NORTH:
		return "N"
	if v == SOUTH:
		return "S"
	return "?"
