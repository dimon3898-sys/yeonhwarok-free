"""Integer frame clocks; seconds are views, never allocation state."""
from fractions import Fraction
import math
class FrameGrid:
    def __init__(self,fps=30):
        self.fps=Fraction(str(fps))
        if self.fps<=0:raise ValueError('FPS_INVALID')
    def frames(self,seconds,mode='nearest'):
        v=Fraction(str(seconds))*self.fps
        return math.ceil(v-Fraction(1,1000000)) if mode=='ceil' else math.floor(v) if mode=='floor' else math.floor(v+Fraction(1,2))
    def seconds(self,frames):
        if not isinstance(frames,int):raise ValueError('FRAME_COUNT_NOT_INTEGER')
        return float(Fraction(frames,1)/self.fps)
    def snap(self,seconds,mode='nearest'):return self.seconds(self.frames(seconds,mode))
    def allocate(self,total,minimums,weights,caps=None):
        if not isinstance(total,int) or any(not isinstance(n,int) or n<=0 for n in minimums):raise ValueError('FRAME_BUDGET_INVALID')
        remaining=total-sum(minimums)
        if remaining<0:raise ValueError('FRAME_BUDGET_EXCEEDED')
        weights=[Fraction(str(w)) for w in weights];denom=sum(weights)
        extras=[math.floor(remaining*w/denom) for w in weights];extras[-1]+=remaining-sum(extras)
        counts=[a+b for a,b in zip(minimums,extras)]
        for i,cap in enumerate(caps or [None]*len(counts)):
            if cap is not None and i!=len(counts)-1:
                excess=max(0,counts[i]-max(minimums[i],cap));counts[i]-=excess;counts[-1]+=excess
        start=0;result=[]
        for count in counts:
            end=start+count
            result.append(dict(start_frame=start,end_frame=end,frame_count=count,start_seconds=self.seconds(start),end_seconds=self.seconds(end),duration=self.seconds(count)))
            start=end
        assert start==total
        return result

def canonicalize_plan(plan,fps=None):
    """New-plan finalization only; loaded historic projects are never migrated."""
    if fps is None:
        from .backends import quality_settings
        fps=quality_settings(plan.get('options',{}).get('quality','HIGH'))['fps']
    clock=FrameGrid(fps);cursor=0;receipts=[]
    temporal={'time','start_time','end_time','duration','initial_hold','move_end','settle','reveal_time','perception_hold','required_hold','next_major_move','total_duration','event_time','start','end'}
    def snap_tree(value):
        if isinstance(value,list):
            for item in value:snap_tree(item)
        elif isinstance(value,dict):
            for key,item in value.items():
                if (key in temporal or key.endswith('_duration') or key=='next_event_lead_time') and isinstance(item,(int,float)) and not isinstance(item,bool):value[key]=clock.snap(item)
                elif key not in ('source_hashes','lighting','lighting_entry','camera_up_start','camera_up_end','information'):snap_tree(item)
    authored=plan.get('metadata',{}).get('reference_blueprint',{}).get('beats',[])
    for index,scene in enumerate(plan['scenes']):
        count=authored[index]['frame_count'] if index<len(authored) and 'frame_count' in authored[index] else clock.frames(scene['duration'])
        end=cursor+count
        scene.update(scene_start_frame=cursor,scene_end_frame=end,frame_count=count)
        scene['start_time']=clock.seconds(cursor);scene['duration']=clock.seconds(count)
        for section in ('visual_events','sound_events','text_events','labels','routes','entities','direction','motion_timing','rhythm_micro_beats'):
            if section in scene:snap_tree(scene[section])
        direction=scene.get('direction',{})
        if direction:
            direction['perception_hold']=clock.seconds(count-clock.frames(direction['reveal_time']))
            direction['settle']=clock.seconds(count-clock.frames(direction['move_end']))
            if direction.get('next_major_move') is not None:direction['next_major_move']=clock.seconds(end)
        receipts.append(dict(scene_id=scene['scene_id'],start_frame=cursor,end_frame=end,frame_count=count,start_seconds=clock.seconds(cursor),end_seconds=clock.seconds(end)))
        cursor=end
    if cursor!=clock.frames(plan['duration']):raise ValueError('FRAME_TOTAL_MISMATCH')
    plan['duration']=clock.seconds(cursor)
    plan['metadata']['frame_grid']=dict(version='INTEGER_FRAME_CLOCK_v014',fps=str(clock.fps),total_frames=cursor,scenes=receipts,gap=0,overlap=0)
    return plan


def validate_frame_plan(plan):
    receipt=plan['metadata']['frame_grid'];clock=FrameGrid(receipt['fps']);cursor=0
    for scene,entry in zip(plan['scenes'],receipt['scenes']):
        count=scene['frame_count']
        if type(count) is not int or count<=0:raise ValueError('FRAME_COUNT_INVALID')
        if scene['scene_start_frame']!=cursor or scene['scene_end_frame']!=cursor+count:raise ValueError('FRAME_BOUNDARY_INVALID')
        if entry['scene_id']!=scene['scene_id'] or entry['start_frame']!=cursor or entry['end_frame']!=cursor+count or entry['frame_count']!=count:raise ValueError('FRAME_RECEIPT_INVALID')
        if abs(scene['duration']*float(clock.fps)-count)>1e-7 or abs(scene['start_time']*float(clock.fps)-cursor)>1e-7:raise ValueError('FRAME_SECONDS_INVALID')
        cursor+=count
    if len(receipt['scenes'])!=len(plan['scenes']) or cursor!=receipt['total_frames'] or cursor!=clock.frames(plan['duration']):raise ValueError('FRAME_TOTAL_MISMATCH')
    return dict(passed=True,total_frames=cursor,gap=0,overlap=0)
