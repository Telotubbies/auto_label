import {
  Activity, BarChart3, Bell, Boxes, BrainCircuit, Cctv, ClipboardCheck, CreditCard, Database, Film, FlaskConical,
  FolderGit2, GitBranch, KeyRound, Layers, LayoutDashboard, LineChart, Rocket, ScrollText, Settings, ShieldCheck,
  Tag, Tags, Upload, Users, Wrench,
} from 'lucide-react'
import type { NavIcon } from '@/lib/nav'

/** One icon registration for every nav renderer (workspace rail, project panel, breadcrumbs). */
export const ICONS: Record<NavIcon, typeof Layers> = {
  projects: Layers, models: Boxes, playground: FlaskConical, deployments: Rocket,
  members: Users, audit: ScrollText, usage: CreditCard, integrations: KeyRound,
  activity: Bell, settings: Settings, admin: ShieldCheck,
  upload: Upload, annotate: Tag, dataset: Database, video: Film, versions: FolderGit2, classes: Tags,
  insights: LineChart, train: BrainCircuit, modelInsights: BarChart3, deploy: Rocket, qa: ClipboardCheck,
  streams: Cctv, access: KeyRound, projectSettings: Wrench,
  lineage: GitBranch, dashboards: LayoutDashboard, streamAnalytics: Activity,
}
