class_name Cardinal
extends RefCounted
## Strict four-direction dash selection.
##
## Walking is eight-way, but a dash always resolves to exactly one of
## North / South / East / West:
##   * the dominant input axis wins;
##   * an exact tie (keyboard diagonals) goes to the axis whose key was pressed
##     most recently (InputCommand.axis_hint) — "the newest key wins";
##   * with no axis hint, ties go to the horizontal axis (East/West);
##   * with no movement held, the dash uses the last valid cardinal facing.

const EAST := Vector2(1, 0)
const WEST := Vector2(-1, 0)
const NORTH := Vector2(0, -1)
const SOUTH := Vector2(0, 1)

const AXIS_UNKNOWN := -1
const AXIS_HORIZONTAL := 0
const AXIS_VERTICAL := 1

## Relative difference under which two axes count as a tie.
const TIE_EPSILON := 0.05


static func from_input(move: Vector2, axis_hint: int, fallback_facing: Vector2) -> Vector2:
	if move.length_squared() < 1e-4:
		return snap(fallback_facing)
	var ax := absf(move.x)
	var ay := absf(move.y)
	var horizontal: bool
	if absf(ax - ay) <= TIE_EPSILON * maxf(ax, ay):
		horizontal = axis_hint != AXIS_VERTICAL
	else:
		horizontal = ax > ay
	if horizontal:
		return EAST if move.x > 0.0 else WEST
	return SOUTH if move.y > 0.0 else NORTH


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
