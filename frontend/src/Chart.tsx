import {Area,AreaChart,CartesianGrid,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';

export function OverviewChart({data}:{data:any[]}){
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{top:12,right:10,left:-16,bottom:0}}>
        <defs>
          <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#68d9bd" stopOpacity={0.25}/>
            <stop offset="95%" stopColor="#68d9bd" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1c2a3d" vertical={false}/>
        <XAxis dataKey="day" tickFormatter={x=>`D${x}`} tick={{fill:'#7e91a8',fontSize:11}} axisLine={false} tickLine={false}/>
        <YAxis yAxisId="l" tick={{fill:'#7e91a8',fontSize:11}} axisLine={false} tickLine={false}/>
        <YAxis yAxisId="r" orientation="right" tick={{fill:'#7e91a8',fontSize:11}} axisLine={false} tickLine={false}/>
        <Tooltip contentStyle={{background:'#101c2c',border:'1px solid #26364b',borderRadius:10,color:'#edf4fb'}}/>
        <Area yAxisId="l" type="monotone" dataKey="sleep" stroke="#68d9bd" strokeWidth={2} fill="url(#fill)"/>
        <Area yAxisId="r" type="monotone" dataKey="heart" stroke="#72a9ff" strokeWidth={2} fill="none"/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function HealthChart({data}:{data:any[]}){
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{top:12,right:10,left:-16,bottom:0}}>
        <CartesianGrid stroke="#1c2a3d" vertical={false}/>
        <XAxis dataKey="day" tickFormatter={x=>`D${x}`} tick={{fill:'#7e91a8',fontSize:11}} axisLine={false} tickLine={false}/>
        <YAxis yAxisId="l" tick={{fill:'#7e91a8',fontSize:11}} axisLine={false} tickLine={false}/>
        <YAxis yAxisId="r" orientation="right" tick={{fill:'#7e91a8',fontSize:11}} axisLine={false} tickLine={false}/>
        <Tooltip contentStyle={{background:'#101c2c',border:'1px solid #26364b',borderRadius:10,color:'#edf4fb'}}/>
        <Area yAxisId="l" type="monotone" dataKey="sleep" stroke="#68d9bd" strokeWidth={2} fill="#68d9bd22"/>
        <Area yAxisId="r" type="monotone" dataKey="heart" stroke="#72a9ff" strokeWidth={2} fill="none"/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

export default HealthChart;
