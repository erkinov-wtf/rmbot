from django.db import models
from django.utils.translation import gettext_lazy as _


class RoleSlug(models.TextChoices):
    SUPER_ADMIN = "super_admin", _("Super Admin")
    OPS_MANAGER = "ops_manager", _("Ops Manager")
    MASTER = "master", _("Master (Service Lead)")
    TECHNICIAN = "technician", _("Technician")
    QC_INSPECTOR = "qc_inspector", _("QC Inspector")


class EmployeeLevel(models.IntegerChoices):
    L1 = 1, _("L1")
    L2 = 2, _("L2")
    L3 = 3, _("L3")
    L4 = 4, _("L4")
    L5 = 5, _("L5")


class AccessRequestStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")


class BikeStatus(models.TextChoices):
    READY = "ready", _("Ready")
    IN_SERVICE = "in_service", _("In Service")
    RENTED = "rented", _("Rented")
    BLOCKED = "blocked", _("Blocked")
    WRITE_OFF = "write_off", _("Write Off")


class TicketStatus(models.TextChoices):
    NEW = "new", _("New")
    ASSIGNED = "assigned", _("Assigned")
    IN_PROGRESS = "in_progress", _("In Progress")
    WAITING_QC = "waiting_qc", _("Waiting QC")
    REWORK = "rework", _("Rework")
    DONE = "done", _("Done")


class WorkSessionStatus(models.TextChoices):
    RUNNING = "running", _("Running")
    PAUSED = "paused", _("Paused")
    STOPPED = "stopped", _("Stopped")


class TicketTransitionAction(models.TextChoices):
    CREATED = "created", _("Created")
    ASSIGNED = "assigned", _("Assigned")
    STARTED = "started", _("Started")
    TO_WAITING_QC = "to_waiting_qc", _("To Waiting QC")
    QC_PASS = "qc_pass", _("QC Pass")
    QC_FAIL = "qc_fail", _("QC Fail")


class XPLedgerEntryType(models.TextChoices):
    ATTENDANCE_PUNCTUALITY = "attendance_punctuality", _("Attendance Punctuality")
    TICKET_BASE_XP = "ticket_base_xp", _("Ticket Base XP")
    TICKET_QC_FIRST_PASS_BONUS = "ticket_qc_first_pass_bonus", _("Ticket QC First Pass Bonus")


class PayrollMonthStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    CLOSED = "closed", _("Closed")
    APPROVED = "approved", _("Approved")
