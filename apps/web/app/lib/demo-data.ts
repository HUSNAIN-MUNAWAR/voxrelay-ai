export type Call = { id:string; caller:string; phone:string; agent:string; state:string; outcome:string; duration:string; score:number; quality:number; time:string; tag:string };
export const calls: Call[] = [
  {id:'call-live-clinic',caller:'Jordan Williams',phone:'+1 (555) 013-9914',agent:'Mira — Patient Intake',state:'Live',outcome:'Booking in progress',duration:'02:18',score:86,quality:96,time:'Now',tag:'Clinic'},
  {id:'call-204',caller:'Eleanor Brooks',phone:'+1 (555) 019-7712',agent:'Relay — Emergency Dispatch',state:'Escalated',outcome:'Human handoff',duration:'01:42',score:99,quality:92,time:'4m ago',tag:'Emergency'},
  {id:'call-203',caller:'Maya Chen',phone:'+1 (555) 014-2288',agent:'Aster — Buyer Concierge',state:'Completed',outcome:'Qualified',duration:'04:12',score:91,quality:94,time:'18m ago',tag:'Real estate'},
  {id:'call-202',caller:'Samir Patel',phone:'+1 (555) 015-4008',agent:'Haven — Resident Support',state:'Completed',outcome:'Work order',duration:'03:08',score:78,quality:90,time:'31m ago',tag:'Property'},
  {id:'call-201',caller:'Nina Alvarez',phone:'+1 (555) 016-2145',agent:'Atlas — Claims Intake',state:'Transferred',outcome:'Claims specialist',duration:'03:46',score:82,quality:88,time:'45m ago',tag:'Insurance'},
  {id:'call-200',caller:'Unknown caller',phone:'+1 (555) 018-0000',agent:'Relay — Emergency Dispatch',state:'Review',outcome:'Low confidence',duration:'00:46',score:22,quality:52,time:'1h ago',tag:'Review'}
];
export const transcript = [
  {speaker:'AI',time:'00:04',text:'Welcome to Meridian Clinic. This call may be recorded. Do I have your permission to continue?',confidence:99},
  {speaker:'Caller',time:'00:09',text:'Yes. I need a new patient appointment for persistent headaches, preferably Wednesday morning.',confidence:96},
  {speaker:'AI',time:'00:17',text:'I can help with that. I will collect a few booking details and offer the next available time.',confidence:99},
  {speaker:'Caller',time:'00:28',text:'Wednesday morning works. My name is Jordan Williams.',confidence:98},
  {speaker:'AI',time:'00:36',text:'I can offer Wednesday at 10:00 AM with our intake clinician. Does that work?',confidence:99},
  {speaker:'Caller',time:'00:44',text:'Yes, please book it. My email is jordan.williams@example.test.',confidence:98}
];
export const trend = [
  {day:'Jul 1',calls:44,bookings:12,quality:87}, {day:'Jul 2',calls:52,bookings:15,quality:89}, {day:'Jul 3',calls:48,bookings:13,quality:91}, {day:'Jul 4',calls:61,bookings:19,quality:88}, {day:'Jul 5',calls:55,bookings:16,quality:92}, {day:'Jul 6',calls:63,bookings:21,quality:93}, {day:'Jul 7',calls:58,bookings:18,quality:91}
];
export const pipeline = [
  {name:'New',total:16,leads:[['Harper Lane',64],['Daniel Okafor',58],['Elena Soto',55]]},
  {name:'Contacted',total:13,leads:[['Theo Mason',71],['Amara Cole',68],['Owen Brooks',53]]},
  {name:'Qualified',total:21,leads:[['Maya Chen',91],['Samir Patel',78],['Nina Alvarez',82]]},
  {name:'Booked',total:14,leads:[['Jordan Williams',86],['Sofia Flores',88],['Luis Martin',79]]},
  {name:'Follow-up',total:9,leads:[['Eleanor Brooks',99],['Unknown caller',22],['Mina Park',67]]}
];
