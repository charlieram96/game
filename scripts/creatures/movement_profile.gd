class_name MovementProfile
extends Resource
## A species' body on the board. Creatures move only by dashing (see
## DashProfile); values are world units (1 unit = 1 board cell).

@export var deceleration: float = 50.0  ## units/second² for leftover velocity.
## Every creature fits inside one cell (radius < 0.5).
@export var collision_radius: float = 0.45
## Relative mass for body-to-body pushing.
@export var mass: float = 1.0
