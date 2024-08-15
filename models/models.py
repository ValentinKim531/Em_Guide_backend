import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Union, Optional, Type, Any

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Integer,
    ForeignKey,
    Time,
    Date,
    DateTime,
    Boolean,
    Uuid,
    func,
    UUID,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class User(Base):
    """
    Model for users in the database.
    """

    __tablename__ = "users"

    userid = Column(String, primary_key=True)
    username = Column(String)
    firstname = Column(String)
    lastname = Column(String)
    fio = Column(String)
    birthdate = Column(Date)
    menstrual_cycle = Column(String)
    country = Column(String)
    city = Column(String)
    medication = Column(String)
    const_medication = Column(String)
    const_medication_name = Column(String)
    reminder_time = Column(Time)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    language = Column(String)
    role = Column(String)

    def __repr__(self):
        return (
            "<userid={}, "
            "username='{}', "
            "firstname='{}', "
            "lastname='{}', "
            "fio='{}', "
            "birthdate='{}', "
            "menstrual_cycle='{}', "
            "country='{}', "
            "city='{}', "
            "medication='{}', "
            "const_medication='{}', "
            "const_medication_name='{}', "
            "reminder_time='{}', "
            "created_at='{}', "
            "updated_at='{}', "
            "language='{}', "
            "role='{}')>"
        ).format(
            self.userid,
            self.username,
            self.firstname,
            self.lastname,
            self.fio,
            self.birthdate,
            self.menstrual_cycle,
            self.country,
            self.city,
            self.medication,
            self.const_medication,
            self.const_medication_name,
            self.reminder_time,
            self.created_at,
            self.updated_at,
            self.language,
            self.role,
        )


class Survey(Base):
    """
    Model for survey in the database.
    """

    __tablename__ = "survey"

    survey_id = Column(Integer, primary_key=True, autoincrement=True)
    userid = Column(
        String,
        ForeignKey("users.userid", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    headache_today = Column(String)
    medicament_today = Column(String)
    pain_intensity = Column(Integer)
    pain_area = Column(String)
    area_detail = Column(String)
    pain_type = Column(String)
    comments = Column(String)

    user = relationship("User", backref="survey")

    def __repr__(self):
        return (
            "<survey_id={}, "
            "userid={}, "
            "created_at='{}', "
            "updated_at='{}', "
            "headache_today='{}', "
            "medicament_today='{}', "
            "pain_intensity='{}', "
            "pain_area='{}', "
            "area_detail='{}', "
            "pain_type='{}', "
            "comments='{}')>"
        ).format(
            self.survey_id,
            self.userid,
            self.created_at,
            self.updated_at,
            self.headache_today,
            self.medicament_today,
            self.pain_intensity,
            self.pain_area,
            self.area_detail,
            self.pain_type,
            self.comments,
        )


class Message(Base):

    __tablename__ = "messages"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id = Column(String, index=True)
    content = Column(String)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_created_by_user = Column(Boolean, default=True)

    def __repr__(self):
        return (
            "<id={}, "
            "user_id={}, "
            "content='{}', "
            "created_at='{}', "
            "is_created_by_user='{}'"
        ).format(
            self.id,
            self.user_id,
            self.content,
            self.created_at,
            self.is_created_by_user,
        )


class Database(ABC):
    """
    Simple Database API
    """

    @abstractmethod
    async def add_entity(
        self, entity_data: any, model_class: type[Base]
    ) -> None:
        """
        Add a new entity to the database.

        :param entity_data: Data of the entity to add. It can be either
        an instance of a model class or a dictionary.
        :param model_class: The class of the model corresponding to the entity.
        """
        pass

    @abstractmethod
    async def get_entity_parameter(
        self,
        model_class: type[Base],
        filters: Optional[dict] = None,
        parameter: Optional[str] = None,
    ) -> Optional[Union[Base, Any]]:
        """
        Get a specific parameter of an entity.

        :param entity_id: The ID of the entity.
        :param parameter: The name of the parameter.
        :param model_class: The class of the model corresponding to the entity.

        :return: The value of the specified parameter.
        """
        pass

    @abstractmethod
    async def get_entities_parameter(
        self, model_class: Type[Base], filters: Optional[dict] = None
    ) -> Optional[list[Base]]:
        """
        Get entities from the database based on filters.

        :param model_class: The class of the model corresponding to the entities.
        :param filters: A dictionary of filters to apply.

        :return: A list of entities.
        """
        pass

    @abstractmethod
    async def get_entities(self, model_class: type[Base]) -> any:
        """
        Retrieve a list of entities from the database.

        :param model_class: The class of the model corresponding to the entity.

        :return: A list of entity objects or None if an error occurs.
        """
        pass

    @abstractmethod
    async def update_entity_parameter(
        self,
        entity_id: Union[int, tuple],
        parameter: str,
        value: any,
        model_class: type[Base],
    ) -> None:
        """
        Update a specific parameter of an entity.

        :param entity_id: The ID of the entity.
        :param parameter: The name of the parameter to update.
        :param value: The new value of the parameter.
        :param model_class: The class of the model corresponding to the entity.
        :param session: The database session to use.

        :return: None
        """
        pass

    @abstractmethod
    async def delete_entity(
        self, entity_id: int, model_class: type[Base]
    ) -> None:
        """
        Delete an entity from the database.

        :param entity_id: The ID of the entity to delete.
        :param model_class: The class of the model corresponding to the entity.

        :return: None
        """
        pass
