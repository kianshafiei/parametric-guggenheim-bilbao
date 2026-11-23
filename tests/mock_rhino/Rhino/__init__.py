"""Bare-minimum stand-in for RhinoCommon so the Grasshopper script can be smoke-tested without Rhino."""
class _M:
    def __init__(self,*a,**k): pass
    def __getattr__(self,n): return _M()
    def __call__(self,*a,**k): return _M()
    def __iter__(self): return iter([_M()])
    def __getitem__(self,i): return _M()
    def __len__(self): return 1
    def __bool__(self): return True
    def __add__(self,o): return _M()
    def __mul__(self,o): return _M()
    def __float__(self): return 1.0
    def __sub__(self,o): return _M()
    def __radd__(self,o): return 1.0
    def __gt__(self,o): return True
    def __lt__(self,o): return False
    def __ge__(self,o): return True
    def __le__(self,o): return False
    def __truediv__(self,o): return 1.0
    def __eq__(self,o): return False
    def __int__(self): return 3
import sys, types
G=types.ModuleType('Rhino.Geometry')
G.__getattr__=lambda n:_M()
sys.modules['Rhino.Geometry']=G
Geometry=G
