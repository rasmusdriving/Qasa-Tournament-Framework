import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brackets.models import Base
target_metadata = Base.metadata