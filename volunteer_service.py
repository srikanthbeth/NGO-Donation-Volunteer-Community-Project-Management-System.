
from sqlalchemy.orm import Session

from models.user import User
from models.volunteer import Volunteer
from repositories.volunteer_repository import VolunteerRepository


class VolunteerService:
    @staticmethod
    def create_profile(
        db: Session,
        user: User,
        data: dict,
    ) -> Volunteer:
        if user.role != "VOLUNTEER":
            raise ValueError("Only volunteer accounts can create a volunteer profile.")

        if not user.is_active:
            raise PermissionError("Inactive users cannot create volunteer profiles.")

        existing = VolunteerRepository.get_by_user_id(db, user.id)
        if existing:
            raise ValueError("A volunteer profile already exists for this user.")

        data["user_id"] = user.id
        data["status"] = "PENDING"

        return VolunteerRepository.create(db, data)

    @staticmethod
    def get_my_profile(db: Session, user: User) -> Volunteer:
        volunteer = VolunteerRepository.get_by_user_id(db, user.id)

        if not volunteer:
            raise LookupError("Volunteer profile not found.")

        return volunteer

    @staticmethod
    def update_profile(
        db: Session,
        volunteer: Volunteer,
        data: dict,
    ) -> Volunteer:
        required_fields = {
            "skills",
            "availability",
            "hours_per_week",
            "experience_years",
        }

        for field in required_fields:
            if field in data and data[field] is None:
                raise ValueError(f"{field} cannot be null.")

        return VolunteerRepository.update(db, volunteer, data)
    
    @staticmethod
    def update_status(
        db: Session,
        volunteer: Volunteer,
        status: str,
    ) -> Volunteer:
        return VolunteerRepository.update(
            db,
            volunteer,
            {"status": status},
        )
