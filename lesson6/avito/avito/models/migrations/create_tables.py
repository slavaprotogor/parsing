import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

from avito import engine
from avito.models.product import Base


Base.metadata.create_all(engine)
