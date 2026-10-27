"""Demo: python demo_vertical_curve.py input.dxf output.csv [vip_index] [length_m]"""
import csv
import sys
from vertical_curve import from_profile_dxf

if __name__ == '__main__':
    source, output = sys.argv[1:3]
    idx = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    length = float(sys.argv[4]) if len(sys.argv) > 4 else 100.0
    alignment = from_profile_dxf(source, {idx: length})
    with open(output, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['STA_m','elevation_m','gradient_permille'])
        writer.writerows(alignment.sample(25))
    for c in alignment.curves:
        print(f'VIP {c.vip_index}: STA {c.vip_sta:.3f}, PVC {c.pvc_sta:.3f}, PVT {c.pvt_sta:.3f}, L={c.length:.3f}')
    print('saved:',output)
