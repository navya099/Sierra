"""Clip longitudinal bridge geometry above the profile-band upper boundary."""

def clip_line_above(a, b, y_min, eps=1e-9):
    ay, by = a[1], b[1]
    ina, inb = ay >= y_min-eps, by >= y_min-eps
    if not ina and not inb:
        return None
    if ina and inb:
        return a, b
    if abs(by-ay) <= eps:
        return None
    t = (y_min-ay)/(by-ay)
    cross = (a[0]+t*(b[0]-a[0]), y_min)
    return (a,cross) if ina else (cross,b)


def clip_polygon_above(vertices, y_min, eps=1e-9):
    """Sutherland-Hodgman clipping for a closed polygon against y>=y_min."""
    if not vertices:
        return []
    output=[]
    prev=vertices[-1]
    for cur in vertices:
        pin=prev[1]>=y_min-eps
        cin=cur[1]>=y_min-eps
        if pin != cin:
            dy=cur[1]-prev[1]
            if abs(dy)>eps:
                t=(y_min-prev[1])/dy
                output.append((prev[0]+t*(cur[0]-prev[0]),y_min))
        if cin:
            output.append(cur)
        prev=cur
    cleaned=[]
    for p in output:
        if not cleaned or abs(cleaned[-1][0]-p[0])>eps or abs(cleaned[-1][1]-p[1])>eps:
            cleaned.append(p)
    if len(cleaned)>1 and all(abs(cleaned[0][k]-cleaned[-1][k])<=eps for k in (0,1)):
        cleaned.pop()
    return cleaned if len(cleaned)>=3 else []
