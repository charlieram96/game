class_name ArenaDefinition
extends Resource
## Shared by the simulation (collision) and the presentation (what to build).
## Coordinates are world XZ with the arena centered on the origin.
##
## Arenas are boards of 1-unit cells (CombatConst.CELL_SIZE): cell (0, 0) has
## its top-left corner at bounds().position. Creatures move by dashing from
## cell to cell, so spawns and standing stones sit on cell centres and every
## creature fits inside one cell.

@export var id: StringName = &"ringstones"
@export var display_name: String = "The Ringstones"
@export var size: Vector2 = Vector2(20, 12)
## Standing stones: (x, z, radius).
@export var circles: PackedVector3Array = PackedVector3Array()
## Solid boxes (crates, walls) in XZ.
@export var boxes: Array[Rect2] = []
@export var spawn_team0: Vector2 = Vector2(-5, 0)
@export var spawn_team1: Vector2 = Vector2(5, 0)
@export var floor_style: StringName = &"sand"
@export var crowd: bool = true


static func ringstones() -> ArenaDefinition:
	var d := ArenaDefinition.new()
	d.id = &"ringstones"
	d.display_name = "The Ringstones"
	d.size = Vector2(20, 12)
	# Point-symmetric so neither side has an advantage; each stone fills a
	# cell. Two pairs break up the long rows and columns: cover from shots
	# and something to dash around.
	d.circles = PackedVector3Array([
		Vector3(-3.5, -2.5, 0.45), Vector3(3.5, 2.5, 0.45),
		Vector3(-6.5, 3.5, 0.45), Vector3(6.5, -3.5, 0.45),
	])
	# The board has an even number of rows, so the spawns sit one row apart
	# (point-symmetric): nobody starts in the other's line of fire.
	d.spawn_team0 = Vector2(-7.5, -0.5)
	d.spawn_team1 = Vector2(7.5, 0.5)
	return d


static func training_yard() -> ArenaDefinition:
	var d := ArenaDefinition.new()
	d.id = &"training_yard"
	d.display_name = "Mossford Training Yard"
	d.size = Vector2(20, 12)
	d.circles = PackedVector3Array()
	d.spawn_team0 = Vector2(-6.5, -0.5)
	d.spawn_team1 = Vector2(3.5, -0.5)
	d.floor_style = &"dirt"
	d.crowd = false
	return d


func bounds() -> Rect2:
	return Rect2(-size * 0.5, size)


func cell_count() -> Vector2i:
	return Vector2i(int(round(size.x / CombatConst.CELL_SIZE)), int(round(size.y / CombatConst.CELL_SIZE)))


## Centre of cell `c` in world XZ.
func cell_center(c: Vector2i) -> Vector2:
	return bounds().position + (Vector2(c) + Vector2(0.5, 0.5)) * CombatConst.CELL_SIZE


## The cell containing world point `p` (may lie outside the board).
func cell_of(p: Vector2) -> Vector2i:
	var local := (p - bounds().position) / CombatConst.CELL_SIZE
	return Vector2i(floori(local.x), floori(local.y))


func has_cell(c: Vector2i) -> bool:
	var n := cell_count()
	return c.x >= 0 and c.y >= 0 and c.x < n.x and c.y < n.y


static func by_id(arena_id: StringName) -> ArenaDefinition:
	match arena_id:
		&"training_yard":
			return training_yard()
		_:
			return ringstones()
