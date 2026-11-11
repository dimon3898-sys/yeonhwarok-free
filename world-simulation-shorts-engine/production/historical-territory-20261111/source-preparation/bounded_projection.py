"""Source-independent adaptive projection for piecewise vector graticules.

The field interface supplies west/east/south/north MonotoneCurve objects,
angular_bounds, and transform(point, allow_extrapolation=True). Each curve
supplies axis and original line/quadratic segments. No source asset, city,
date, geography, renderer, or coordinate repair is embedded here.

Required transform contract: lon = west + (east-west)*(x-L(y))/(R(y)-L(y));
lat = south + (north-south)*(B(x)-y)/(B(x)-T(x)). These analytic bounds are
not valid for an arbitrary unrelated transform implementation. Curves must be
monotone in their input axis, and input coordinates must be within their
original vector domains. Angular bounds must use geographic degrees.
"""
import math

# Conservative upper length per angular degree, for lon/lat metric error only.
METRES_PER_ANGULAR_DEGREE_UPPER=112000.0


def curve_segment_stats(curve,value):
    for s in curve.segments:
        if min(s[0][curve.axis],s[-1][curve.axis]) <= value <= max(s[0][curve.axis],s[-1][curve.axis]):
            break
    else:raise ValueError('OUTSIDE_GRATICULE_SOURCE_SEGMENT')
    axis=curve.axis; other=1-axis
    lo=min(p[other] for p in s); hi=max(p[other] for p in s)
    if len(s)==2:
        slope=abs((s[1][other]-s[0][other])/(s[1][axis]-s[0][axis]))
        return lo,hi,slope,0.
    p,c,q=s
    da=[2*(c[k]-p[k])for k in (0,1)]
    db=[2*(q[k]-c[k])for k in (0,1)]
    minimum=min(abs(da[axis]),abs(db[axis]))
    assert da[axis]*db[axis]>0 and minimum>0
    slope=max(abs(da[other]),abs(db[other]))/minimum
    # d2(other)/d(axis)2 = (other''*axis' - other'*axis'')/axis'^3.
    second=[db[k]-da[k]for k in (0,1)]
    numerator=abs(second[other]*da[axis]-da[other]*second[axis])
    curvature=numerator/minimum**3
    return lo,hi,slope,curvature


def derivative_bounds(field,bbox):
    xmin,ymin,xmax,ymax=bbox; xmid=(xmin+xmax)/2; ymid=(ymin+ymax)/2
    L=curve_segment_stats(field.west,ymid); R=curve_segment_stats(field.east,ymid)
    B=curve_segment_stats(field.south,xmid); T=curve_segment_stats(field.north,xmid)
    D=R[0]-L[1]; H=B[0]-T[1]
    assert D>0 and H>0
    A=max(abs(xmin-L[1]),abs(xmax-L[0])); C=max(abs(B[0]-ymax),abs(B[1]-ymin))
    D1=R[2]+L[2]; D2=R[3]+L[3]; H1=B[2]+T[2]; H2=B[3]+T[3]
    west,south,east,north=field.angular_bounds
    lon_span=abs(east-west); lat_span=abs(north-south)
    lon_j=(lon_span/D,lon_span*(L[2]/D+A*D1/D**2))
    lat_j=(lat_span*(B[2]/H+C*H1/H**2),lat_span/H)
    lon_h=(0.,lon_span*D1/D**2,lon_span*(L[3]/D+2*L[2]*D1/D**2+A*D2/D**2+2*A*D1**2/D**3))
    lat_h=(lat_span*(B[3]/H+2*B[2]*H1/H**2+C*H2/H**2+2*C*H1**2/H**3),lat_span*H1/H**2,0.)
    return lon_j,lat_j,lon_h,lat_h


def split_at_grid_knots(field,a,b):
    """Split at every piecewise derivative discontinuity before bounding F''."""
    values={0.,1.}
    for curve in (field.west,field.east,field.south,field.north):
        axis=curve.axis
        if a[axis]==b[axis]:continue
        for segment in curve.segments[:-1]:
            t=(segment[-1][axis]-a[axis])/(b[axis]-a[axis])
            if 0<t<1:values.add(t)
    return [tuple(a[k]+t*(b[k]-a[k]) for k in (0,1)) for t in sorted(values)]


class AdaptiveProjection:
    def __init__(self,field,tolerance_metres=1.):
        if not math.isfinite(tolerance_metres) or tolerance_metres<=0:
            raise ValueError('POSITIVE_FINITE_PROJECTION_TOLERANCE_REQUIRED')
        if len(field.angular_bounds)!=4 or not all(math.isfinite(v)for v in field.angular_bounds):
            raise ValueError('FINITE_GEOGRAPHIC_ANGULAR_BOUNDS_REQUIRED')
        self.field=field; self.tolerance=tolerance_metres
        self.accepted=[];self.maximum_bound=0.;self.max_depth=0
        self.cache={}
    def transform(self,p):
        p=tuple(p)
        if len(p)!=2 or not all(math.isfinite(v)for v in p):
            raise ValueError('FINITE_NATIVE_2D_COORDINATE_REQUIRED')
        if p not in self.cache:self.cache[p]=self.field.transform(p,allow_extrapolation=True)
        return self.cache[p]
    def smooth_edge(self,a,b,output,depth=0):
        bbox=(min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))
        _,_,lon_h,lat_h=derivative_bounds(self.field,bbox)
        vx=abs(b[0]-a[0]);vy=abs(b[1]-a[1])
        bounds=[h[0]*vx*vx+2*h[1]*vx*vy+h[2]*vy*vy for h in (lon_h,lat_h)]
        error=math.hypot(*bounds)*METRES_PER_ANGULAR_DEGREE_UPPER/8
        # Small explicit floating-point roundoff budget; geometry is never nudged.
        error=error*(1+1e-12)+1e-7
        if error<=self.tolerance:
            pa,pb=self.transform(a),self.transform(b)
            output.append(pb);self.maximum_bound=max(self.maximum_bound,error)
            self.max_depth=max(self.max_depth,depth)
            self.accepted.append((a,b,pa,pb,error))
            return
        if depth>=32:raise ValueError('PROJECTION_ERROR_TOLERANCE_NOT_REACHED')
        m=tuple((a[k]+b[k])/2 for k in (0,1))
        self.smooth_edge(a,m,output,depth+1);self.smooth_edge(m,b,output,depth+1)
    def edge(self,a,b,output):
        splits=split_at_grid_knots(self.field,a,b)
        for a,b in zip(splits,splits[1:]):self.smooth_edge(a,b,output)
    def ring(self,ring):
        output=[self.transform(ring[0])]
        for a,b in zip(ring,ring[1:]):self.edge(a,b,output)
        assert output[0]==output[-1]
        return output
    def geometry(self,geometry):
        polygons=geometry['coordinates'] if geometry['type']=='MultiPolygon' else [geometry['coordinates']]
        coords=[[self.ring(ring)for ring in poly]for poly in polygons]
        return {'type':'MultiPolygon','coordinates':coords}
    def independent_sample_bound_check(self):
        """New transform check only; supplements, rather than defines, algebraic bound."""
        worst=0.;failures=[]
        for a,b,pa,pb,bound in self.accepted:
            for t in (.125,.25,.375,.5,.625,.75,.875):
                source=[a[k]+t*(b[k]-a[k])for k in (0,1)]
                actual=self.transform(source); chord=[pa[k]+t*(pb[k]-pa[k])for k in (0,1)]
                error=math.dist(actual,chord)*METRES_PER_ANGULAR_DEGREE_UPPER
                worst=max(worst,error)
                if error>bound:failures.append({'a':a,'b':b,'t':t,'observedErrorMetres':error,'boundMetres':bound})
        return {'sampledMaximumErrorMetres':worst,'boundExceedances':failures,'sampleFractions':[.125,.25,.375,.5,.625,.75,.875]}

