class_name HitSpec
extends Resource
## What happens when a hitbox connects. Shared by every ability component that
## can deal damage, so hit feel (hitstop, hitstun, knockback) is tuned in one
## consistent vocabulary.

enum KnockbackMode {
	DIRECTIONAL,  ## Along the hitbox direction (projectiles, slashes, lines).
	RADIAL,  ## Away from the hitbox center (bursts, rings, pounds).
	NONE,
}

@export var power: float = 5.0
## Empty = use the ability's element.
@export var element: StringName = &""
@export var knockback: float = 0.5  ## World units of push.
@export var knockback_mode: KnockbackMode = KnockbackMode.DIRECTIONAL
@export var hitstun_ticks: int = 10  ## Flinch duration on an unguarded hit.
@export var hitstop_ticks: int = 3  ## Freeze frames applied to both parties.
@export var guardable: bool = true
## Melee hits that are perfect-guarded stagger the attacker.
@export var staggers_on_perfect_guard: bool = true
## 0 = each target can be hit once per hitbox; >0 = re-hit interval.
@export var rehit_interval_ticks: int = 0
@export var statuses: Array[StatusApplication] = []
@export_group("Presentation")
@export var hit_sfx: StringName = &"hit_light"
@export var hit_vfx: StringName = &"hit_spark"
