class_name ArenaDefinition
extends Resource
## Shared by the simulation (collision) and the presentation (what to build).
## Coordinates are world XZ with the arena centered on the origin.

@export var id: StringName = &"ringstones"
@export var display_name: String = "The Ringstones"
@export var size: Vector2 = Vector2(16, 10)
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
	d.size = Vector2(14, 9)
	# Point-symmetric so neither side has an advantage.
	d.circles = PackedVector3Array([Vector3(-2.3, -1.9, 0.55), Vector3(2.3, 1.9, 0.55)])
	d.spawn_team0 = Vector2(-4.8, 0)
	d.spawn_team1 = Vector2(4.8, 0)
	return d


static func training_yard() -> ArenaDefinition:
	var d := ArenaDefinition.new()
	d.id = &"training_yard"
	d.display_name = "Mossford Training Yard"
	d.size = Vector2(13, 8)
	d.circles = PackedVector3Array()
	d.spawn_team0 = Vector2(-4, 0)
	d.spawn_team1 = Vector2(3, 0)
	d.floor_style = &"dirt"
	d.crowd = false
	return d


static func by_id(arena_id: StringName) -> ArenaDefinition:
	match arena_id:
		&"training_yard":
			return training_yard()
		_:
			return ringstones()
