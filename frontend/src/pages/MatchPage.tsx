import React, { useState, useEffect } from "react"
import { api } from "../lib/api"
import { Progress } from "../components/ui/Progress"
import { Badge } from "../components/ui/Badge"
import { Modal } from "../components/ui/Modal"
import { Play, CheckCircle, AlertTriangle, Search, ChevronRight } from "lucide-react"
import toast from "react-hot-toast"

interface Job {
  id: string;
  title: string;
  company?: string;
  seniority_level?: string;
}

interface MatchResult {
  id: string;
  candidate_id: string;
  jd_id: string;
  total_score: number;
  semantic_score: number;
  skill_score: number;
  experience_score: number;
  matched_skills: string[];
  missing_skills: string[];
  explanation_summary: string;
  explanation_detail?: any; // To store detailed fetched data
}



function MatchDetailView({ jdId, candId }: { jdId: string, candId: string }) {
  const [detail, setDetail] = useState<any>(null);
  
  useEffect(() => {
    api.get(`/match/${jdId}/${candId}`).then(res => setDetail(res.data)).catch(err => console.error(err));
  }, [jdId, candId]);

  if (!detail) return <div className="space-y-4"><div className="h-4 bg-slate-200 animate-pulse rounded w-1/2"></div><div className="h-20 bg-slate-200 animate-pulse rounded"></div></div>;

  return (
    <div className="space-y-6">
      <div className="bg-indigo-50 dark:bg-indigo-900/20 p-4 rounded-lg border border-indigo-100 dark:border-indigo-800">
        <h3 className="font-semibold text-indigo-900 dark:text-indigo-100 mb-2">AI Summary</h3>
        <p className="text-sm text-indigo-700 dark:text-indigo-300 leading-relaxed">{detail.summary}</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <h4 className="font-medium flex items-center"><CheckCircle className="w-4 h-4 mr-2 text-green-500"/> Matched Skills</h4>
          <div className="flex flex-wrap gap-2">
            {detail.matched_skills.map((s: string) => <Badge key={s} variant="success">{s}</Badge>)}
            {detail.matched_skills.length === 0 && <span className="text-sm text-slate-500">None</span>}
          </div>
          
          <h4 className="font-medium flex items-center pt-4"><AlertTriangle className="w-4 h-4 mr-2 text-red-500"/> Missing Skills</h4>
          <div className="flex flex-wrap gap-2">
            {detail.missing_skills.map((s: string) => <Badge key={s} variant="destructive">{s}</Badge>)}
            {detail.missing_skills.length === 0 && <span className="text-sm text-slate-500">None</span>}
          </div>
        </div>

        <div className="space-y-4">
           <h4 className="font-medium">Score Breakdown</h4>
           <div>
             <div className="flex justify-between text-xs mb-1"><span>Semantic Match</span><span>{(detail.score_breakdown.semantic * 100).toFixed(0)}%</span></div>
             <Progress value={detail.score_breakdown.semantic * 100} indicatorClassName="bg-blue-500" />
           </div>
           <div>
             <div className="flex justify-between text-xs mb-1"><span>Skill Overlap</span><span>{(detail.score_breakdown.skill * 100).toFixed(0)}%</span></div>
             <Progress value={detail.score_breakdown.skill * 100} indicatorClassName="bg-purple-500" />
           </div>
           <div>
             <div className="flex justify-between text-xs mb-1"><span>Experience Match</span><span>{(detail.score_breakdown.experience * 100).toFixed(0)}%</span></div>
             <Progress value={detail.score_breakdown.experience * 100} indicatorClassName="bg-yellow-500" />
           </div>
           <p className="text-xs text-slate-500 italic mt-2">Experience Assessment: {detail.experience_assessment}</p>
        </div>
      </div>

      {detail.flags && detail.flags.length > 0 && (
        <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
           <h4 className="font-medium mb-3">Detected Flags</h4>
           <div className="flex gap-2">
             {detail.flags.map((f: string) => <Badge key={f} variant="warning">{f}</Badge>)}
           </div>
        </div>
      )}
    </div>
  )
}

export function MatchPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJd, setSelectedJd] = useState<string>("");
  
  const [isMatching, setIsMatching] = useState(false);
  const [_pollingStatus, setPollingStatus] = useState<string>("");
  const [pollProgress, setPollProgress] = useState<string>("");
  
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [candidateNames, setCandidateNames] = useState<Record<string, string>>({}); // Hacky cache map because standard schema returns FK id
  
  const [selectedMatch, setSelectedMatch] = useState<MatchResult | null>(null);

  useEffect(() => {
    // Load jobs initially
    api.get("/jobs").then(res => setJobs(res.data)).catch((_err) => {});
    // Precach candidate names
    api.get("/candidates?limit=1000").then(res => {
        const map: Record<string, string> = {};
        res.data.forEach((c: any) => map[c.id] = c.name);
        setCandidateNames(map);
    }).catch((_err) => {});
  }, []);

  const handleSelectJob = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const jdId = e.target.value;
    setSelectedJd(jdId);
    setMatches([]);
    // Optional: Preload cached matches if they already exist
    if(jdId) {
       api.get(`/match/${jdId}?limit=20`).then(res => setMatches(res.data)).catch(() => {});
    }
  }

  const handleRunMatch = async () => {
    if(!selectedJd) return toast.error("Select a Job Description first");
    
    setIsMatching(true);
    setMatches([]);
    setPollingStatus("Triggering match job...");
    
    try {
      const res = await api.post(`/match/trigger/${selectedJd}`);
      const actId = res.data.job_id;
      
      // Polling loop
      const interval = setInterval(async () => {
         try {
           const statRes = await api.get(`/match/status/${actId}`);
           const st = statRes.data;
           
           if(st.status === 'SUCCESS' || st.status === 'complete') {
             clearInterval(interval);
             setPollingStatus("Matching complete!");
             setIsMatching(false);
             // Fetch actual ranked matches
             const matchRes = await api.get(`/match/${selectedJd}?limit=20`);
             setMatches(matchRes.data);
             toast.success("Matching computation finished");
           } else if (st.status === 'FAILURE' || st.status === 'failed') {
             clearInterval(interval);
             setIsMatching(false);
             setPollingStatus("Matching failed.");
             toast.error("Celery task failed");
           } else {
             setPollingStatus(`Processing matches...`);
             setPollProgress(st.progress || "Unknown");
           }
         } catch(e) {
           console.error("Poll err", e);
         }
      }, 2000);
      
    } catch(err: any) {
      setIsMatching(false);
      toast.error(err.response?.data?.detail || "Failed to trigger match");
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.7) return "success";
    if (score >= 0.4) return "warning";
    return "destructive";
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Candidate Matching Engine</h1>
        <p className="text-slate-500">Run bulk ranking and semantic vector comparisons.</p>
      </div>

      <div className="bg-white dark:bg-slate-900 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row gap-4 items-end">
        <div className="flex-1 w-full">
          <label className="block text-sm font-medium mb-1 text-slate-700 dark:text-slate-300">Target Job Description</label>
          <select 
            className="w-full p-2.5 border rounded-lg dark:bg-slate-800 dark:border-slate-700 focus:ring-2 focus:ring-indigo-500"
            value={selectedJd}
            onChange={handleSelectJob}
            disabled={isMatching}
          >
            <option value="">-- Select a Job Description --</option>
            {jobs.map(j => (
              <option key={j.id} value={j.id}>{j.title} {j.company ? `(${j.company})` : ''}</option>
            ))}
          </select>
        </div>
        <button 
          onClick={handleRunMatch}
          disabled={!selectedJd || isMatching}
          className="flex items-center justify-center py-2.5 px-6 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-all disabled:opacity-50 min-w-[200px]"
        >
          {isMatching ? (
            <div className="flex items-center">
              <div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Running... {pollProgress}
            </div>
          ) : (
            <>
              <Play className="w-4 h-4 mr-2" />
              Compute Matches
            </>
          )}
        </button>
      </div>

      {/* Results Section */}
      {!isMatching && selectedJd && matches.length === 0 && (
         <div className="text-center p-12 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 border-dashed rounded-xl">
           <Search className="w-12 h-12 text-slate-300 mx-auto mb-4" />
           <h3 className="text-lg font-medium text-slate-700 dark:text-slate-200 mb-1">No Matches Found</h3>
           <p className="text-slate-500">Run compute to analyze candidates against this position.</p>
         </div>
      )}
      
      {jobs.length === 0 && (
         <div className="text-center p-12 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl">
           <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
           <h3 className="text-lg font-medium text-amber-800 dark:text-amber-200 mb-1">No Job Descriptions Available</h3>
           <p className="text-amber-700 dark:text-amber-400">Head over to the Upload tab to add some job descriptions first.</p>
         </div>
      )}

      {matches.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold flex items-center">
            <Search className="w-5 h-5 mr-2" /> Top Ranked Candidates
          </h2>
          
          <div className="grid gap-4">
            {matches.map((m, idx) => (
              <div key={m.id} className="bg-white dark:bg-slate-900 p-5 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row gap-4 items-center transition-all hover:shadow-md">
                 <div className="font-bold text-lg text-slate-300 w-8 text-center">#{idx + 1}</div>
                 <div className="flex-1 min-w-0">
                   <h3 className="font-semibold text-lg text-slate-900 dark:text-slate-100 truncate">{candidateNames[m.candidate_id] || 'Unknown Candidate'}</h3>
                   <div className="flex flex-wrap items-center gap-2 mt-1">
                     <Badge variant={getScoreColor(m.total_score)}>
                       Total Score: {(m.total_score * 100).toFixed(0)}%
                     </Badge>
                     {m.matched_skills.map((s, i) => i < 3 && <span key={s} className="text-xs text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">{s}</span>)}
                     {m.matched_skills.length > 3 && <span className="text-xs text-slate-400">+{m.matched_skills.length - 3} more</span>}
                   </div>
                 </div>
                 <div className="w-full sm:w-48 space-y-1">
                    <div className="flex justify-between text-xs"><span>Skill Match</span><span>{(m.skill_score * 100).toFixed(0)}%</span></div>
                    <Progress value={m.skill_score * 100} indicatorClassName="bg-indigo-500" />
                 </div>
                 <button 
                  onClick={() => setSelectedMatch(m)}
                  className="p-2 ml-0 sm:ml-2 text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 rounded-lg transition-colors flex items-center"
                 >
                   Details <ChevronRight className="w-4 h-4 ml-1" />
                 </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedMatch && (
        <Modal isOpen={!!selectedMatch} onClose={() => setSelectedMatch(null)} title={`Match Details: ${candidateNames[selectedMatch.candidate_id] || 'Candidate'}`}>
           <MatchDetailView jdId={selectedMatch.jd_id} candId={selectedMatch.candidate_id} />
        </Modal>
      )}
    </div>
  )
}

