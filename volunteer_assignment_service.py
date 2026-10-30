
from datetime import date

from sqlalchemy.orm import Session

from models.user import User
from models.volunteer import Volunteer
from models.volunteer_assignment import VolunteerAssignment
from repositories.volunteer_assignment_repository import (
    VolunteerAssignmentRepository,
)


STAFF_ROLES = {
    "SUPER_ADMIN",
    "NGO_MANAGER",
    "VOLUNTEER_COORDINATOR",
}

ALLOWED_TRANSITIONS = {
    "ASSIGNED": {"ACCEPTED", "CANCELLED"},
    "ACCEPTED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def get_role(user: User) -> str:
    role = user.role
    return str(getattr(role, "value", role)).upper()


class VolunteerAssignmentService:

    @staticmethod
    def create_assignment(
        db: Session,
        current_user: User,
        data: dict,
    ) -> VolunteerAssignment:
        if get_role(current_user) not in STAFF_ROLES:
            raise PermissionError(
                "Only authorized staff can create volunteer assignments."
            )

        volunteer = db.get(Volunteer, data["volunteer_id"])

        if volunteer is None:
            raise LookupError("Volunteer profile not found.")

        if volunteer.status != "ACTIVE":
            raise ValueError(
                "Only active volunteers can receive assignments."
            )

        if not volunteer.user.is_active:
            raise ValueError(
                "Inactive user accounts cannot receive assignments."
            )

        start_date = data["start_date"]
        end_date = data.get("end_date")

        if end_date is not None and end_date < start_date:
            raise ValueError(
                "End date cannot be earlier than start date."
            )

        if data.get("hours_per_week", 0) > volunteer.hours_per_week:
            raise ValueError(
                "Assignment hours cannot exceed the volunteer's "
                "available hours per week."
            )

        data["assigned_by"] = current_user.id
        data["status"] = "ASSIGNED"

        return VolunteerAssignmentRepository.create(db, data)

    @staticmethod
    def get_assignment(
        db: Session,
        current_user: User,
        assignment_id: int,
    ) -> VolunteerAssignment:
        assignment = VolunteerAssignmentRepository.get_by_id(
            db, assignment_id
        )

        if assignment is None:
            raise LookupError("Volunteer assignment not found.")

        if get_role(current_user) in STAFF_ROLES:
            return assignment

        volunteer = VolunteerAssignmentService._get_user_volunteer(
            db, current_user
        )

        if assignment.volunteer_id != volunteer.id:
            raise PermissionError(
                "You cannot access another volunteer's assignment."
            )

        return assignment

    @staticmethod
    def update_assignment(
        db: Session,
        current_user: User,
        assignment_id: int,
        data: dict,
    ) -> VolunteerAssignment:
        if get_role(current_user) not in STAFF_ROLES:
            raise PermissionError(
                "Only authorized staff can edit assignment details."
            )

        assignment = VolunteerAssignmentRepository.get_by_id(
            db, assignment_id
        )

        if assignment is None:
            raise LookupError("Volunteer assignment not found.")

        if assignment.status in {"COMPLETED", "CANCELLED"}:
            raise ValueError(
                "Completed or cancelled assignments cannot be edited."
            )

        # Validate the final dates, not just dates supplied in the request.
        final_start = data.get("start_date", assignment.start_date)
        final_end = data.get("end_date", assignment.end_date)

        if final_end is not None and final_end < final_start:
            raise ValueError(
                "End date cannot be earlier than start date."
            )

        if (
            "hours_per_week" in data
            and data["hours_per_week"] is None
        ):
            raise ValueError("hours_per_week cannot be null.")

        volunteer = VolunteerAssignmentService._get_volunteer_by_id(
            db, assignment.volunteer_id
        )

        final_hours = data.get(
            "hours_per_week", assignment.hours_per_week
        )

        if final_hours > volunteer.hours_per_week:
            raise ValueError(
                "Assignment hours cannot exceed the volunteer's "
                "available hours per week."
            )

        return VolunteerAssignmentRepository.update(
            db, assignment, data
        )

    @staticmethod
    def update_status(
        db: Session,
        current_user: User,
        assignment_id: int,
        new_status: str,
    ) -> VolunteerAssignment:
        assignment = VolunteerAssignmentRepository.get_by_id(
            db, assignment_id
        )

        if assignment is None:
            raise LookupError("Volunteer assignment not found.")

        role = get_role(current_user)

        if role in STAFF_ROLES:
            allowed = ALLOWED_TRANSITIONS.get(assignment.status, set())

            if new_status not in allowed:
                raise ValueError(
                    f"Cannot change assignment status from "
                    f"{assignment.status} to {new_status}."
                )

        else:
            volunteer = VolunteerAssignmentService._get_user_volunteer(
                db, current_user
            )

            if assignment.volunteer_id != volunteer.id:
                raise PermissionError(
                    "You cannot update another volunteer's assignment."
                )

            # Volunteers may accept their assignment or begin work
            # after accepting it. Staff controls completion/cancellation.
            if new_status not in {"ACCEPTED", "IN_PROGRESS"}:
                raise PermissionError(
                    "Volunteers may only accept assignments or mark "
                    "accepted assignments as in progress."
                )

            allowed = ALLOWED_TRANSITIONS.get(assignment.status, set())

            if new_status not in allowed:
                raise ValueError(
                    f"Cannot change assignment status from "
                    f"{assignment.status} to {new_status}."
                )

        return VolunteerAssignmentRepository.update(
            db, assignment, {"status": new_status}
        )

    @staticmethod
    def list_assignments(
        db: Session,
        current_user: User,
        page: int = 1,
        page_size: int = 10,
        volunteer_id: int | None = None,
        project_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[VolunteerAssignment], int]:
        if get_role(current_user) in STAFF_ROLES:
            return VolunteerAssignmentRepository.list(
                db,
                page=page,
                page_size=page_size,
                volunteer_id=volunteer_id,
                project_id=project_id,
                status=status,
                search=search,
            )

        volunteer = VolunteerAssignmentService._get_user_volunteer(
            db, current_user
        )

        # Non-staff users can only see their own assignments.
        if volunteer_id is not None and volunteer_id != volunteer.id:
            raise PermissionError(
                "You cannot view another volunteer's assignments."
            )

        return VolunteerAssignmentRepository.list(
            db,
            page=page,
            page_size=page_size,
            volunteer_id=volunteer.id,
            project_id=project_id,
            status=status,
            search=search,
        )

    @staticmethod
    def _get_user_volunteer(
        db: Session,
        user: User,
    ) -> Volunteer:
        volunteer = db.query(Volunteer).filter(
            Volunteer.user_id == user.id
        ).first()

        if volunteer is None:
            raise LookupError("Volunteer profile not found.")

        return volunteer

    @staticmethod
    def _get_volunteer_by_id(
        db: Session,
        volunteer_id: int,
    ) -> Volunteer:
        volunteer = db.get(Volunteer, volunteer_id)

        if volunteer is None:
            raise LookupError("Volunteer profile not found.")

        return volunteer
