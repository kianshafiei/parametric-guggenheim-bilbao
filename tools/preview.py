"""Quick matplotlib preview of the geometry core without Rhino:  python tools/preview.py out.png '{\"pinch\": 0.45}'"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import core
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
params=json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
m=core.build(open(ROOT / 'data/osm_raw.txt').read(), params)
def loft_quads(secs, closed=True):
    q=[]
    for a,b in zip(secs[:-1],secs[1:]):
        n=len(a)
        for j in range(n if closed else n-1):
            k=(j+1)%n; q.append([a[j],a[k],b[k],b[j]])
    return q
views=[(30,-65),(14,15),(60,-90),(12,-120)]
fig=plt.figure(figsize=(18,12))
for vi,(el,az) in enumerate(views):
    ax=fig.add_subplot(2,2,vi+1,projection='3d')
    polys=[];cols=[]
    for s in m['stone']:
        P=s['poly']; z0=s['z0']; z1=z0+s['h']
        for i in range(len(P)-1):
            polys.append([(P[i][0],P[i][1],z0),(P[i+1][0],P[i+1][1],z0),(P[i+1][0],P[i+1][1],z1),(P[i][0],P[i][1],z1)]); cols.append('#dcd2ba')
        polys.append([(x,y,z1) for x,y in P]); cols.append('#d2c8ae')
    for h in m['hulls']:
        for q in loft_quads(h['sections']): polys.append(q); cols.append('#a7b0ba')
        polys.append(h['sections'][-1]); cols.append('#a7b0ba')
    for q in loft_quads(m['gallery'],closed=False): polys.append(q); cols.append('#b3bbc4')
    for nm in ['tower','hook']:
        for q in loft_quads(m[nm]): polys.append(q); cols.append('#a3acb6')
        polys.append(m[nm][-1]); cols.append('#a3acb6')
    for pet in m['petals']:
        for q in loft_quads(pet,closed=False): polys.append(q); cols.append('#c9d4de')
    ax.add_collection3d(Poly3DCollection(polys,facecolors=cols,edgecolors='#4a4a4a',linewidths=0.08))
    for B in m['bridge']: ax.plot([p[0] for p in B],[p[1] for p in B],[m['deck_z']]*len(B),'r-',lw=1)
    for Q in m['quay']: ax.plot([p[0] for p in Q],[p[1] for p in Q],[0]*len(Q),'b-',lw=0.8)
    ax.set_xlim(-95,140); ax.set_ylim(-90,95); ax.set_zlim(0,80); ax.set_box_aspect((235,185,80)); ax.view_init(el,az); ax.set_axis_off()
plt.subplots_adjust(0,0,1,1,0,0); plt.savefig(sys.argv[1] if len(sys.argv)>1 else 'preview.png',dpi=65)
