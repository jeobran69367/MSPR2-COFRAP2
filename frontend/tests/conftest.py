import os
import sys

# frontend/app/main.py référence "app/static" et "app/templates" en chemins
# relatifs : il faut donc que le cwd soit déjà positionné sur frontend/ et
# que "frontend/" soit sur sys.path AVANT que pytest importe app.main (donc
# au chargement de ce conftest, pas dans une fixture qui s'exécute trop tard).
FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if FRONTEND_DIR not in sys.path:
    sys.path.insert(0, FRONTEND_DIR)

os.chdir(FRONTEND_DIR)
