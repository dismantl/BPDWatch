"""overtime_pay default 0

Revision ID: b4145ba7d4c6
Revises: 86eb228e4bc0
Create Date: 2020-09-27 14:43:58.704560

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4145ba7d4c6'
down_revision = '86eb228e4bc0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute('update salaries set overtime_pay = 0 where overtime_pay is null')
    op.alter_column('salaries', 'overtime_pay',
                    existing_type=sa.NUMERIC(),
                    server_default='0',
                    nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('salaries', 'overtime_pay',
                    existing_type=sa.NUMERIC(),
                    nullable=True)
    # ### end Alembic commands ###
