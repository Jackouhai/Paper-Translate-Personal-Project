import React, { useState } from 'react';
import { 
  FileText, 
  Upload, 
  History, 
  Settings, 
  HelpCircle, 
  Download, 
  Copy, 
  Plus, 
  Minus, 
  User,
  ChevronRight,
  Menu,
  X,
  ArrowRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// --- Utilities ---
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- Components ---

const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'outline' | 'ghost', size?: 'sm' | 'md' | 'lg' }>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => {
    const variants = {
      primary: 'canvas-gradient text-white shadow-md hover:brightness-110',
      secondary: 'bg-white text-primary border border-outline-variant hover:bg-surface-container',
      outline: 'bg-transparent border border-primary text-primary hover:bg-primary/5',
      ghost: 'bg-transparent text-secondary hover:bg-surface-container-high',
    };
    const sizes = {
      sm: 'px-3 py-1.5 text-xs',
      md: 'px-6 py-2 text-sm',
      lg: 'px-8 py-4 text-lg',
    };
    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center rounded-xl font-bold transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none',
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    );
  }
);

// --- Main App ---

export default function App() {
  const [view, setView] = useState<'landing' | 'workspace'>('landing');
  const [isUploading, setIsUploading] = useState(false);

  const handleUpload = () => {
    setIsUploading(true);
    setTimeout(() => {
      setIsUploading(false);
      setView('workspace');
    }, 1500);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <AnimatePresence mode="wait">
        {view === 'landing' ? (
          <LandingPage key="landing" onUpload={handleUpload} isUploading={isUploading} />
        ) : (
          <Workspace key="workspace" onBack={() => setView('landing')} />
        )}
      </AnimatePresence>
    </div>
  );
}

// --- Landing Page View ---

function LandingPage({ onUpload, isUploading }: { onUpload: () => void, isUploading: boolean, key?: string }) {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col min-h-screen"
    >
      {/* Header */}
      <header className="fixed top-0 w-full z-50 bg-surface/80 backdrop-blur-md border-b border-outline-variant/20 h-16 px-8 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl font-extrabold tracking-tight text-on-surface font-headline">Paper Translate</span>
        </div>
        <nav className="hidden md:flex items-center space-x-8">
          <a href="#" className="text-primary font-bold border-b-2 border-primary pb-1 text-sm">Home</a>
          <a href="#" className="text-on-surface/70 hover:text-primary transition-colors text-sm font-medium">Features</a>
          <a href="#" className="text-on-surface/70 hover:text-primary transition-colors text-sm font-medium">Pricing</a>
        </nav>
        <Button size="md">Sign In</Button>
      </header>

      <main className="flex-1 pt-16 flex flex-col items-center justify-center px-6 relative overflow-hidden">
        {/* Decorative Blurs */}
        <div className="absolute top-[-10%] right-[-5%] w-[40vw] h-[40vw] bg-primary/5 rounded-full blur-[100px] -z-10" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[30vw] h-[30vw] bg-primary/5 rounded-full blur-[100px] -z-10" />

        <div className="max-w-4xl w-full text-center mb-12">
          <motion.h1 
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-5xl md:text-7xl font-extrabold tracking-tight text-on-surface mb-6 leading-tight font-headline"
          >
            Translate your PDFs with <span className="text-primary">Precision.</span>
          </motion.h1>
          <motion.p 
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="text-lg md:text-xl text-on-surface/60 max-w-2xl mx-auto"
          >
            Transform complex PDF documents into semantic HTML while preserving layout, fonts, and structural integrity. The digital architect for your content.
          </motion.p>
        </div>

        {/* Upload Zone */}
        <motion.div 
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="w-full max-w-3xl aspect-[16/10] bg-surface-container/50 rounded-[2rem] p-4 relative group cursor-pointer transition-all duration-300 hover:bg-primary/5 border-2 border-dashed border-transparent hover:border-primary/20"
          onClick={onUpload}
        >
          <div className="w-full h-full bg-white rounded-[1.5rem] flex flex-col items-center justify-center whisper-shadow border border-outline-variant/10">
            {isUploading ? (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin mb-4" />
                <p className="text-primary font-bold">Processing Document...</p>
              </div>
            ) : (
              <>
                <div className="mb-6 w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center text-primary">
                  <Upload size={40} />
                </div>
                <h3 className="text-2xl font-bold mb-2 font-headline">Drag & Drop PDF</h3>
                <p className="text-on-surface/50 mb-8">or click to browse from your computer</p>
                <Button size="lg">Choose File</Button>
                <p className="mt-8 text-[10px] font-bold tracking-widest uppercase text-on-surface/40">Maximum file size: 50MB</p>
              </>
            )}
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="bg-surface border-t border-outline-variant/20 px-8 py-6 flex flex-col md:flex-row items-center justify-between gap-4">
        <p className="text-on-surface/40 text-xs font-medium">© 2024 Paper Translate. The Digital Curator.</p>
        <div className="flex gap-8">
          <a href="#" className="text-on-surface/60 hover:text-primary text-xs font-medium">Privacy Policy</a>
          <a href="#" className="text-on-surface/60 hover:text-primary text-xs font-medium">Terms of Service</a>
          <a href="#" className="text-on-surface/60 hover:text-primary text-xs font-medium">Contact Support</a>
        </div>
      </footer>
    </motion.div>
  );
}

// --- Workspace View ---

function Workspace({ onBack }: { onBack: () => void, key?: string }) {
  const [viewMode, setViewMode] = useState<'html' | 'pdf'>('html');

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col h-screen overflow-hidden"
    >
      {/* Top Nav */}
      <nav className="h-16 bg-white border-b border-outline-variant/20 px-8 flex items-center justify-between shrink-0 z-50">
        <div className="flex items-center gap-8">
          <span className="text-xl font-extrabold tracking-tight text-primary font-headline cursor-pointer" onClick={onBack}>Paper Translate</span>
          <div className="hidden md:flex items-center gap-6">
            <a href="#" className="text-primary font-bold border-b-2 border-primary pb-1 text-sm">Home</a>
            <a href="#" className="text-on-surface/70 hover:text-primary transition-colors text-sm font-medium">Features</a>
            <a href="#" className="text-on-surface/70 hover:text-primary transition-colors text-sm font-medium">Pricing</a>
          </div>
        </div>
        <Button size="md">Sign In</Button>
      </nav>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-surface border-r border-outline-variant/20 flex flex-col p-4 shrink-0">
          <div className="mb-6 px-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white">
                <FileText size={20} />
              </div>
              <div>
                <p className="font-headline font-bold text-sm text-primary">Workspace</p>
                <p className="text-[10px] text-on-surface/40 uppercase tracking-widest font-bold">Active Session</p>
              </div>
            </div>
          </div>

          <Button className="mb-4 w-full" onClick={onBack}>
            New Translation
          </Button>

          <nav className="space-y-1 flex-1">
            <SidebarItem icon={<History size={18} />} label="History" />
            <SidebarItem icon={<FileText size={18} />} label="Documents" active />
            <SidebarItem icon={<Settings size={18} />} label="Settings" />
            <SidebarItem icon={<HelpCircle size={18} />} label="Help" />
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col bg-surface-container/30 overflow-hidden">
          {/* Toolbar */}
          <div className="h-14 bg-white border-b border-outline-variant/20 px-6 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <FileText size={18} className="text-primary" />
                <span className="text-sm font-bold text-on-surface">quantum_computing_v3.pdf</span>
              </div>
              <div className="h-6 w-[1px] bg-outline-variant/30" />
              
              {/* View Switcher */}
              <div className="flex items-center bg-surface-container p-1 rounded-lg">
                <button 
                  onClick={() => setViewMode('html')}
                  className={cn(
                    "px-4 py-1.5 text-xs font-bold rounded-md transition-all",
                    viewMode === 'html' ? "bg-white text-primary shadow-sm" : "text-on-surface/50 hover:text-on-surface"
                  )}
                >
                  HTML View
                </button>
                <button 
                  onClick={() => setViewMode('pdf')}
                  className={cn(
                    "px-4 py-1.5 text-xs font-bold rounded-md transition-all",
                    viewMode === 'pdf' ? "bg-white text-primary shadow-sm" : "text-on-surface/50 hover:text-on-surface"
                  )}
                >
                  Original PDF
                </button>
              </div>

              <div className="h-6 w-[1px] bg-outline-variant/30" />
              
              {/* Zoom */}
              <div className="flex items-center gap-2">
                <button className="p-1 hover:bg-surface-container rounded-md text-on-surface/50"><Minus size={16} /></button>
                <span className="text-xs font-bold w-10 text-center">100%</span>
                <button className="p-1 hover:bg-surface-container rounded-md text-on-surface/50"><Plus size={16} /></button>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" className="gap-2">
                <Copy size={14} /> Copy Code
              </Button>
              <Button size="sm" className="gap-2">
                <Download size={14} /> Download
              </Button>
            </div>
          </div>

          {/* Document Canvas */}
          <div className="flex-1 overflow-y-auto p-8 md:p-12">
            <motion.div 
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="max-w-4xl mx-auto bg-white rounded-2xl shadow-xl min-h-[1100px] p-12 md:p-20 border border-outline-variant/10"
            >
              {viewMode === 'html' ? <TranslatedContent /> : <div className="flex items-center justify-center h-full text-on-surface/20 font-bold text-2xl uppercase tracking-widest">PDF Preview Not Available</div>}
            </motion.div>
          </div>
        </main>
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-outline-variant/20 px-8 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <span className="text-primary font-black tracking-tighter text-lg">PT</span>
          <p className="text-[10px] font-bold text-on-surface/40 uppercase tracking-widest">© 2024 Paper Translate • The Digital Curator</p>
        </div>
        <div className="flex gap-8">
          <a href="#" className="text-[10px] font-bold text-on-surface/40 hover:text-primary uppercase tracking-widest transition-colors">Privacy</a>
          <a href="#" className="text-[10px] font-bold text-on-surface/40 hover:text-primary uppercase tracking-widest transition-colors">Terms</a>
          <a href="#" className="text-[10px] font-bold text-on-surface/40 hover:text-primary uppercase tracking-widest transition-colors">Support</a>
        </div>
      </footer>
    </motion.div>
  );
}

function SidebarItem({ icon, label, active = false }: { icon: React.ReactNode, label: string, active?: boolean }) {
  return (
    <a 
      href="#" 
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all",
        active 
          ? "bg-white text-primary font-bold shadow-sm" 
          : "text-on-surface/60 hover:bg-surface-container-high"
      )}
    >
      {icon}
      <span className="text-sm font-headline">{label}</span>
    </a>
  );
}

function TranslatedContent() {
  return (
    <article className="max-w-none">
      <header className="mb-12 border-b border-outline-variant/20 pb-10">
        <p className="text-primary font-extrabold tracking-[0.2em] uppercase text-[10px] mb-4">Research Translation • Published 2024</p>
        <h1 className="text-4xl md:text-5xl font-black text-on-surface leading-tight font-headline mb-6">Scalable Architectures for Quantum Error Correction</h1>
        <div className="flex items-center gap-6 text-sm text-on-surface/60 font-bold">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center text-primary">
              <User size={14} />
            </div>
            <span>Dr. Elena Rostova</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary/30"></span>
            <span>Theoretical Physics Institute</span>
          </div>
        </div>
      </header>

      <div className="space-y-8 text-on-surface/70 leading-relaxed text-lg">
        <p className="first-letter:text-6xl first-letter:font-black first-letter:text-primary first-letter:mr-4 first-letter:float-left first-letter:mt-1">
          The evolution of quantum computing has reached a critical bottleneck in the form of decoherence. In this paper, we explore a novel approach to surface code implementation that leverages high-density lattice arrangements. Unlike previous models, this architectural blueprint focuses on minimizing physical qubit overhead while maintaining high fault-tolerance thresholds.
        </p>

        <h2 className="text-2xl font-black text-on-surface pt-8 pb-2 font-headline border-l-4 border-primary pl-6">1. Topological Constraints</h2>
        <p>
          Current limitations in superconducting circuits necessitate a shift toward topological protection. Our simulation results indicate a 14% improvement in gate fidelity when applying the proposed hexagonal tiling method. This shift in geometry allows for more efficient syndrome measurement cycles, effectively reducing the noise floor of the system.
        </p>

        <div className="my-12 p-10 bg-surface-container/20 border-l-[6px] border-primary shadow-sm rounded-r-xl">
          <p className="text-xl font-bold italic text-on-surface leading-snug">
            "The transition from linear error suppression to multidimensional lattice stability is no longer a theoretical preference; it is a structural necessity."
          </p>
          <div className="mt-6 flex items-center gap-3">
            <div className="h-[1px] w-8 bg-primary"></div>
            <p className="text-xs font-black text-primary uppercase tracking-widest">Section 4.2: Geometric Synergies</p>
          </div>
        </div>

        <h2 className="text-2xl font-black text-on-surface pt-8 pb-2 font-headline border-l-4 border-primary pl-6">2. Implementation Strategy</h2>
        <p>
          To realize this architecture, we propose a three-tier execution layer. The primary layer manages the physical state of the transmon qubits, while the secondary layer handles the fast-feedback logic required for real-time error detection. The final layer—the orchestration shell—abstracts these complexities into a logical qubit interface accessible by standard quantum algorithms.
        </p>

        <figure className="my-14 group">
          <div className="w-full aspect-video rounded-2xl shadow-2xl overflow-hidden relative">
            <img 
              className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" 
              src="https://picsum.photos/seed/quantum/1200/800" 
              alt="Quantum visualization"
              referrerPolicy="no-referrer"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-80"></div>
            <div className="absolute bottom-0 left-0 right-0 p-6 flex items-end">
              <div className="bg-primary px-3 py-1 rounded-sm mr-4 text-[10px] font-black text-white uppercase tracking-tighter">Fig 1</div>
              <figcaption className="text-white text-xs font-bold opacity-90 italic">Simulation of parity-check connectivity in a 256-qubit array.</figcaption>
            </div>
          </div>
        </figure>

        <p>
          In conclusion, the proposed architecture provides a scalable path forward for the next generation of quantum processors. By rethinking the physical arrangement and measurement protocols, we can achieve the stability required for meaningful computational advantage.
        </p>
      </div>
    </article>
  );
}
