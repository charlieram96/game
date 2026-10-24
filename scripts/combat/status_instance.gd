class_name StatusInstance
extends RefCounted
## A status effect currently applied to a fighter.

var def: StatusEffectDefinition
var ticks_left: int = 0
var duration: int = 0
var source_id: int = -1
var source_attack: float = 10.0
var interval_counter: int = 0
