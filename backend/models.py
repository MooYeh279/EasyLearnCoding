from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from database import Base
import enum


class TopicStatus(str, enum.Enum):
    draft = "draft"
    generating_outline = "generating_outline"
    outline_ready = "outline_ready"
    generating_content = "generating_content"
    content_ready = "content_ready"


class LessonType(str, enum.Enum):
    concept = "concept"
    example = "example"
    exercise = "exercise"
    summary = "summary"


class CodeBlockType(str, enum.Enum):
    example = "example"
    template = "template"
    solution = "solution"


class Language(Base):
    __tablename__ = "languages"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    env_config = Column(JSON, nullable=True, comment="User-customized environment config (e.g. runtime_path)")


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False)
    title = Column(String(200), nullable=False)
    language = relationship("Language")
    topics = relationship("Topic", back_populates="course", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(200), nullable=False)
    status = Column(SAEnum(TopicStatus), default=TopicStatus.draft, nullable=False)
    generation_progress = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    course = relationship("Course", back_populates="topics")
    sections = relationship("Section", back_populates="topic", cascade="all, delete-orphan")
    outline = relationship("TopicOutline", back_populates="topic", uselist=False, cascade="all, delete-orphan")


class TopicOutline(Base):
    __tablename__ = "topic_outlines"
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, unique=True)
    sections_json = Column(JSON, nullable=False)
    feedback_history = Column(JSON, default=list)
    topic = relationship("Topic", back_populates="outline")


class Section(Base):
    __tablename__ = "sections"
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    title = Column(String(200), nullable=False)
    order = Column(Integer, nullable=False)
    topic = relationship("Topic", back_populates="sections")
    lessons = relationship("Lesson", back_populates="section", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    title = Column(String(200), nullable=False)
    order = Column(Integer, nullable=False)
    content = Column(Text, nullable=False, default="")
    lesson_type = Column(SAEnum(LessonType), default=LessonType.concept, nullable=False)
    section = relationship("Section", back_populates="lessons")
    code_blocks = relationship("CodeBlock", back_populates="lesson", cascade="all, delete-orphan")
    exercises = relationship("Exercise", back_populates="lesson", cascade="all, delete-orphan")


class CodeBlock(Base):
    __tablename__ = "code_blocks"
    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False)
    code = Column(Text, nullable=False)
    type = Column(SAEnum(CodeBlockType), default=CodeBlockType.example, nullable=False)
    executable = Column(Integer, default=1)
    lesson = relationship("Lesson", back_populates="code_blocks")


class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    question = Column(Text, nullable=False)
    template = Column(Text, default="")
    test_cases = Column(Text, default="")
    solution = Column(Text, default="")
    lesson = relationship("Lesson", back_populates="exercises")


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
