import sys, math
sys.path.insert(0,"products/dog-bowl/generator"); sys.path.insert(0,"shared")
import numpy as np, trimesh
import cooper_bowl_design as d
R_OUT,R_WALL,R_IN = d.STAND_OD/2, d.WALL_OUTER_R, d.WALL_INNER_R
H,TOP_Z,BASE_H = d.STAND_HEIGHT, d.TOP_BOTTOM, d.BASE_HEIGHT
R_SEAT,SEAT_Z = d.BOWL_SEAT_D/2, d.SEAT_Z
R_OPEN, FLOOR = 68.0, 4.0
zc = TOP_Z - (R_IN - R_OPEN)
flare = TOP_Z - (R_OUT - R_WALL)
profile = np.array([
    [0,0],[R_OUT,0],[R_OUT,BASE_H],[R_WALL,BASE_H],[R_WALL,flare],
    [R_OUT,TOP_Z],[R_OUT,H],[R_SEAT,H],[R_SEAT,SEAT_Z],[R_OPEN,TOP_Z],
    [R_IN,zc],[R_IN,FLOOR],[0,FLOOR],[0,0],
])
m = trimesh.creation.revolve(profile, sections=256)
m.export("/tmp/proto/onepiece_final.stl")
n,a,c = m.face_normals, m.area_faces, m.triangles_center
onbed = c[:,2] < m.bounds[0][2]+0.5
down = (n[:,2] < -1e-6) & ~onbed
ang = np.degrees(np.arcsin(np.clip(-n[down][:,2],0,1)))
print(f"  hollow single piece: watertight={m.is_watertight} volume={m.volume/1000:.0f} cm3")
print(f"  support needed: {a[down][ang>45].sum():.0f} mm2")
bowl = d.visual_bowl()
inter = trimesh.boolean.intersection([m,bowl], engine="manifold")
print(f"  bowl clash: {inter.volume/1000:.3f} cm3")
cur = sum(trimesh.load_mesh(f"out/flush3/meshes/{f}.stl",process=False).volume
          for f in ("cooper_base","cooper_paw_panel","cooper_top_seat_ring"))
print(f"  current three parts total: {cur/1000:.0f} cm3")
