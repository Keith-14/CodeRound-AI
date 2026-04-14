
import { Link, Outlet, useLocation } from "react-router-dom"
import { Briefcase, Upload, Network } from "lucide-react"

export function Layout() {
  const location = useLocation();

  const navLinks = [
    { name: "Upload Data", path: "/upload", icon: Upload },
    { name: "Match Candidates", path: "/match", icon: Network }
  ];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#111827] text-slate-900 dark:text-slate-50">
      {/* Navbar */}
      <nav className="sticky top-0 z-40 w-full backdrop-blur flex-none transition-colors duration-500 lg:z-50 lg:border-b lg:border-slate-900/10 dark:border-slate-50/[0.06] bg-white/95 dark:bg-[#111827]/90">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <Briefcase className="h-8 w-8 text-indigo-600 dark:text-indigo-500 mr-2" />
                <span className="font-bold text-xl tracking-tight text-slate-800 dark:text-white">
                  MatchEngine
                </span>
              </div>
              <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
                {navLinks.map((link) => {
                  const Icon = link.icon;
                  const isActive = location.pathname.startsWith(link.path);
                  return (
                    <Link
                      key={link.name}
                      to={link.path}
                      className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors ${
                        isActive
                          ? "border-indigo-500 text-slate-900 dark:text-white"
                          : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 dark:hover:border-slate-700"
                      }`}
                    >
                      <Icon className="w-4 h-4 mr-2" />
                      {link.name}
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="w-full px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}

