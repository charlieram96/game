class_name DashPlan
extends RefCounted
## Where a dash would go, worked out from the board before it starts. The
## simulation executes exactly this plan and the aiming preview draws it, so
## what the player sees while dragging is what happens.

enum Result { OK, BLOCKED, NO_STAMINA, INVALID }

var result: Result = Result.INVALID
var dir_index: int = -1
var dir: Vector2 = Vector2.ZERO
var cells_requested: int = 0
## Cells actually travelled: walls and stones shorten a dash; a foe standing
## on the landing cell lengthens it by one (the ram carries you past).
var cells: int = 0
## The cell the dash starts from (the creature gathers onto its centre).
var home_cell: Vector2i = Vector2i.ZERO
var home: Vector2 = Vector2.ZERO
var target_cell: Vector2i = Vector2i.ZERO
var target: Vector2 = Vector2.ZERO
## Cells entered, in order; the landing cell is last.
var path: Array[Vector2i] = []
## First cell the dash could not enter, if a wall or stone cut it short.
var blocked: bool = false
var blocked_cell: Vector2i = Vector2i.ZERO
## Foes whose bodies lie on the path, and which of them can be rammed now.
var crosses: Array[int] = []
var rams: Array[int] = []
var extended: bool = false
var cost: float = 0.0
var travel_ticks: int = 0


func ok() -> bool:
	return result == Result.OK
