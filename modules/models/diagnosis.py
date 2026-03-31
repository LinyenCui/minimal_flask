"""
醫療診斷碼資料模型（Phase 1：純結構化表）

設計原則：一個診斷概念 = 一筆資料，ICD-9 和 ICD-10 各一個欄位
- icd9_code 存現有碼（多碼用 " / " 分隔，如 "401.1 / 401.9"）
- icd10_code 隨時可補填，不影響既有資料
- additional_codes 存「需另加之代碼」（如 "N18.-"、"I50.-、N18.-"）

未來擴展 pgvector：只需加 embedding = Column(Vector(768)) 即可接向量搜尋
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from modules.models.base import db


class DiagnosisChapter(db.Model):
    __tablename__ = 'diagnosis_chapters'

    id = Column(Integer, primary_key=True)
    chapter_number = Column(Integer, unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    source_photos = Column(Text)

    code_links = relationship('DiagnosisCodeChapter', back_populates='chapter', lazy='dynamic')


class DiagnosisCode(db.Model):
    __tablename__ = 'diagnosis_codes'

    id = Column(Integer, primary_key=True)
    icd9_code = Column(String(30), index=True)
    icd10_code = Column(String(30), index=True)
    name_zh = Column(String(200), nullable=False)
    name_en = Column(String(200))
    aliases = Column(Text)
    subcategory = Column(String(100))
    is_high_frequency = Column(Boolean, default=False)
    is_handwritten = Column(Boolean, default=False)
    is_deprecated = Column(Boolean, default=False)
    confidence = Column(String(20), default='confirmed')
    description = Column(Text)
    usage_note = Column(Text)
    additional_codes = Column(String(200))

    chapter_links = relationship('DiagnosisCodeChapter', back_populates='diagnosis_code', lazy='joined')
    components = relationship(
        'DiagnosisCodeComponent', back_populates='combined_code',
        foreign_keys='DiagnosisCodeComponent.combined_code_id',
    )
    notes = relationship('DiagnosisCodeNote', back_populates='diagnosis_code')


class DiagnosisCodeChapter(db.Model):
    __tablename__ = 'diagnosis_code_chapters'

    id = Column(Integer, primary_key=True)
    diagnosis_code_id = Column(Integer, ForeignKey('diagnosis_codes.id'), nullable=False)
    chapter_id = Column(Integer, ForeignKey('diagnosis_chapters.id'), nullable=False)

    diagnosis_code = relationship('DiagnosisCode', back_populates='chapter_links')
    chapter = relationship('DiagnosisChapter', back_populates='code_links')

    __table_args__ = (
        UniqueConstraint('diagnosis_code_id', 'chapter_id', name='uq_dx_code_chapter'),
    )


class DiagnosisCodeComponent(db.Model):
    __tablename__ = 'diagnosis_code_components'

    id = Column(Integer, primary_key=True)
    combined_code_id = Column(Integer, ForeignKey('diagnosis_codes.id'), nullable=False)
    component_code = Column(String(20), nullable=False)
    component_order = Column(Integer, nullable=False)
    component_name_zh = Column(String(200))

    combined_code = relationship(
        'DiagnosisCode', back_populates='components',
        foreign_keys=[combined_code_id],
    )


class DiagnosisCodeNote(db.Model):
    __tablename__ = 'diagnosis_code_notes'

    id = Column(Integer, primary_key=True)
    diagnosis_code_id = Column(Integer, ForeignKey('diagnosis_codes.id'), nullable=True)
    chapter_id = Column(Integer, ForeignKey('diagnosis_chapters.id'), nullable=True)
    note_type = Column(String(50))
    note_text = Column(Text, nullable=False)

    diagnosis_code = relationship('DiagnosisCode', back_populates='notes')
    chapter = relationship('DiagnosisChapter')
