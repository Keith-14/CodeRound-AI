import React, { useState, useRef } from "react"
import { uploadBulkFile, api } from "../lib/api"
import { UploadCloud, FileType, CheckCircle, Database, X } from "lucide-react"
import toast from "react-hot-toast"

function DragDropZone({ title, type, endpoint }: { title: string, type: 'jobs' | 'candidates', endpoint: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async () => {
    if (!file) return;
    setIsUploading(true);
    try {
      const res = await uploadBulkFile(endpoint, file);
      toast.success(`${res.length} ${type} uploaded successfully!`);
      setFile(null);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Upload failed. Please check CSV format.";
      toast.error(msg);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex flex-col bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
      <div className="p-5 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center">
          <Database className="w-5 h-5 mr-2 text-indigo-500" />
          {title}
        </h3>
      </div>
      
      <div className="p-6">
        {!file ? (
          <div
            className={`flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-lg transition-colors cursor-pointer ${
              isDragOver ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20" : "border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
            }`}
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadCloud className={`w-10 h-10 mb-3 ${isDragOver ? "text-indigo-500" : "text-slate-400"}`} />
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Click or drag file to this area to upload</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Supports CSV and JSON bulk files</p>
            <input 
              type="file" 
              className="hidden" 
              ref={fileInputRef} 
              onChange={(e) => {
                if (e.target.files?.length) setFile(e.target.files[0])
              }}
              accept=".csv,.json"
            />
          </div>
        ) : (
          <div className="flex flex-col space-y-4">
            <div className="flex items-center justify-between p-4 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg border border-indigo-100 dark:border-indigo-800">
              <div className="flex items-center space-x-3">
                <FileType className="w-8 h-8 text-indigo-500" />
                <div>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate max-w-[200px]">{file.name}</p>
                  <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
              <button onClick={() => setFile(null)} className="p-1 hover:bg-indigo-100 dark:hover:bg-indigo-800 rounded-full transition-colors">
                <X className="w-5 h-5 text-indigo-500" />
              </button>
            </div>
            
            <button
              onClick={handleSubmit}
              disabled={isUploading}
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors focus:ring-4 focus:ring-indigo-100 dark:focus:ring-indigo-900 disabled:opacity-70 flex items-center justify-center"
            >
              {isUploading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                "Upload File"
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function TagInput({ label, tags, setTags }: { label: string, tags: string[], setTags: (tags: string[]) => void }) {
  const [val, setVal] = useState("");
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const newTag = val.trim();
      if (newTag && !tags.includes(newTag)) {
        setTags([...tags, newTag]);
        setVal("");
      }
    }
  };

  const removeTag = (t: string) => {
    setTags(tags.filter(tag => tag !== t));
  };

  return (
    <div className="flex flex-col space-y-2">
      <label className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</label>
      <div className="flex flex-wrap gap-2 mb-2">
        {tags.map(t => (
          <span key={t} className="inline-flex items-center px-2 py-1 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 text-xs">
            {t}
            <button type="button" onClick={() => removeTag(t)} className="ml-1 hover:text-indigo-900 dark:hover:text-indigo-100">
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
      </div>
      <input 
        type="text" 
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type and press enter..."
        className="px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
      />
    </div>
  )
}

function ManualJDForm() {
  const [formData, setFormData] = useState({ title: "", company: "", description: "", experience_years_min: "", experience_years_max: "", seniority_level: "" });
  const [reqSkills, setReqSkills] = useState<string[]>([]);
  const [prefSkills, setPrefSkills] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.post("/jobs", {
        ...formData,
        experience_years_min: formData.experience_years_min ? parseInt(formData.experience_years_min) : null,
        experience_years_max: formData.experience_years_max ? parseInt(formData.experience_years_max) : null,
        required_skills: reqSkills,
        preferred_skills: prefSkills
      });
      toast.success("Job Description created successfully!");
      setFormData({ title: "", company: "", description: "", experience_years_min: "", experience_years_max: "", seniority_level: "" });
      setReqSkills([]); setPrefSkills([]);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error creating JD");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Title *</label>
          <input required type="text" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Company</label>
          <input type="text" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.company} onChange={e => setFormData({...formData, company: e.target.value})} />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1 dark:text-slate-300">Description *</label>
        <textarea required rows={4} className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} />
      </div>
      
      <TagInput label="Required Skills" tags={reqSkills} setTags={setReqSkills} />
      <TagInput label="Preferred Skills" tags={prefSkills} setTags={setPrefSkills} />
      
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Min Years</label>
          <input type="number" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.experience_years_min} onChange={e => setFormData({...formData, experience_years_min: e.target.value})} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Max Years</label>
          <input type="number" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.experience_years_max} onChange={e => setFormData({...formData, experience_years_max: e.target.value})} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Seniority</label>
          <select className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.seniority_level} onChange={e => setFormData({...formData, seniority_level: e.target.value})}>
            <option value="">Any</option>
            <option value="junior">Junior</option>
            <option value="mid">Mid</option>
            <option value="senior">Senior</option>
            <option value="lead">Lead</option>
          </select>
        </div>
      </div>

      <button disabled={isSubmitting} type="submit" className="w-full py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50">
        {isSubmitting ? "Saving..." : "Save Job Description"}
      </button>
    </form>
  )
}

function ManualCandForm() {
  const [formData, setFormData] = useState({ name: "", email: "", resume_text: "", current_role: "", years_of_experience: "" });
  const [skills, setSkills] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.post("/candidates", {
        ...formData,
        years_of_experience: formData.years_of_experience ? parseFloat(formData.years_of_experience) : null,
        skills
      });
      toast.success("Candidate created successfully!");
      setFormData({ name: "", email: "", resume_text: "", current_role: "", years_of_experience: "" });
      setSkills([]);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error creating Candidate");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Name *</label>
          <input required type="text" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Email *</label>
          <input required type="email" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})} />
        </div>
      </div>
      
      <div>
        <label className="block text-sm font-medium mb-1 dark:text-slate-300">Resume Text *</label>
        <textarea required rows={5} className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.resume_text} onChange={e => setFormData({...formData, resume_text: e.target.value})} />
      </div>

      <TagInput label="Skills" tags={skills} setTags={setSkills} />

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Current Role</label>
          <input type="text" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.current_role} onChange={e => setFormData({...formData, current_role: e.target.value})} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1 dark:text-slate-300">Years of Experience</label>
          <input type="number" step="0.5" className="w-full p-2 border rounded dark:bg-slate-800 dark:border-slate-700" value={formData.years_of_experience} onChange={e => setFormData({...formData, years_of_experience: e.target.value})} />
        </div>
      </div>

      <button disabled={isSubmitting} type="submit" className="w-full py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50">
        {isSubmitting ? "Saving..." : "Save Candidate"}
      </button>
    </form>
  )
}

export function UploadPage() {
  const [activeTab, setActiveTab] = useState<'bulk' | 'manual'>('bulk');

  return (
    <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Data Upload</h1>
          <p className="text-slate-500">Add job descriptions and candidates to the matching engine.</p>
        </div>
        
        <div className="bg-slate-200 dark:bg-slate-800 p-1 rounded-lg flex space-x-1">
          <button 
            onClick={() => setActiveTab('bulk')}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${activeTab === 'bulk' ? 'bg-white dark:bg-slate-700 shadow text-indigo-600 dark:text-indigo-400' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}
          >
            Bulk Upload
          </button>
          <button 
            onClick={() => setActiveTab('manual')}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${activeTab === 'manual' ? 'bg-white dark:bg-slate-700 shadow text-indigo-600 dark:text-indigo-400' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}
          >
            Manual Entry
          </button>
        </div>
      </div>

      {activeTab === 'bulk' ? (
        <div className="grid md:grid-cols-2 gap-8">
          <DragDropZone title="Upload Job Descriptions" type="jobs" endpoint="/jobs/bulk" />
          <DragDropZone title="Upload Candidates" type="candidates" endpoint="/candidates/bulk" />
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-8">
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
            <h2 className="text-lg font-semibold mb-4 border-b pb-2 dark:border-slate-800">New Job Description</h2>
            <ManualJDForm />
          </div>
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
            <h2 className="text-lg font-semibold mb-4 border-b pb-2 dark:border-slate-800">New Candidate</h2>
            <ManualCandForm />
          </div>
        </div>
      )}
    </div>
  )
}
