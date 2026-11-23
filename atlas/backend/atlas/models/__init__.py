"""Modelos de datos de ATLAS. Importar todo aquí para que Alembic los vea."""

from atlas.models.base import Base
from atlas.models.core import ActivityLog, Setting
from atlas.models.gym import BodyMetric, Exercise, Routine, RoutineExercise, WorkoutSet
from atlas.models.email import EmailMessage
from atlas.models.money import Budget, HealthDay, PaperTrade
from atlas.models.nutrition import Food, MealEntry
from atlas.models.memory import Conversation, ConversationMessage, Memory
from atlas.models.domain import (
    CalendarEvent,
    Goal,
    GoalProgress,
    Project,
    Task,
    Transaction,
    WorkoutSession,
)

__all__ = [
    "Base",
    "Setting",
    "ActivityLog",
    "Task",
    "CalendarEvent",
    "Transaction",
    "WorkoutSession",
    "Project",
    "Memory",
    "Goal",
    "Budget",
    "PaperTrade",
    "HealthDay",
    "EmailMessage",
    "Food",
    "MealEntry",
    "Exercise",
    "Routine",
    "RoutineExercise",
    "WorkoutSet",
    "BodyMetric",
    "GoalProgress",
    "Conversation",
    "ConversationMessage",
]
