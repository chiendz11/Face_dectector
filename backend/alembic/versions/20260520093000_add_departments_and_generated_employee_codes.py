"""add department master data and employee department references

Revision ID: 20260520093000
Revises: 20260518120000
Create Date: 2026-05-20 09:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260520093000"
down_revision = "20260518120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_departments_code", "departments", ["code"])
    op.create_index("ix_departments_id", "departments", ["id"])

    op.add_column("employees", sa.Column("department_id", sa.Integer(), nullable=True))
    op.create_index("ix_employees_department_id", "employees", ["department_id"])
    op.create_foreign_key(
        "fk_employees_department_id_departments",
        "employees",
        "departments",
        ["department_id"],
        ["id"],
    )

    op.execute(
        """
        INSERT INTO departments (code, name)
        SELECT
          UPPER(REGEXP_REPLACE(TRIM(department), '[^A-Za-z0-9]+', '-', 'g')) AS code,
          TRIM(department) AS name
        FROM employees
        WHERE department IS NOT NULL AND TRIM(department) <> ''
        GROUP BY TRIM(department)
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE employees
        SET department_id = departments.id
        FROM departments
        WHERE employees.department IS NOT NULL
          AND TRIM(employees.department) = departments.name
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_employees_department_id_departments", "employees", type_="foreignkey")
    op.drop_index("ix_employees_department_id", table_name="employees")
    op.drop_column("employees", "department_id")
    op.drop_index("ix_departments_id", table_name="departments")
    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_table("departments")
