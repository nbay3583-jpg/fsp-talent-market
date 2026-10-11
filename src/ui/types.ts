export interface Reason {
  code: string;
  text: string;
  skill: string | null;
}
export interface SkillView {
  skill: string;
  verified_level: string | null;
  verified_sublevel: string | null;
  has_professional_experience: boolean;
  fsp_achievements: string[];
  claimed_only: boolean;
}
export interface PublicCandidate {
  candidate_id: number;
  display_name: string;
  specialization?: string | null;
  invitation_id?: number | null;
  invitation_status?: string | null;
  claimed_grade: string | null;
  verification_status: string;
  verified_grade: string | null;
  verified_sublevel: string | null;
  work_formats: string[];
  location: string | null;
  salary_expectation: { min: number; type: string } | null;
  has_fsp: boolean;
  work_experience?: { position: string; company: string; start_date: string; end_date: string | null; stack: string[]; confirmed: boolean }[];
  skills: SkillView[];
}
export interface Fit {
  eligible?: boolean;
  exclusions?: string[];
  requirement_fit?: number;
  requirement_fit_label?: string;
  components?: Record<string, number>;
  why?: Reason[];
  gaps?: Reason[];
}
export interface MatchRow {
  rank: number;
  requirement_fit: number;
  requirement_fit_label: string;
  why: Reason[];
  gaps: Reason[];
  candidate: PublicCandidate;
}
export interface Contacts {
  full_name: string;
  email: string;
  phone: string | null;
}
export interface Invitation {
  id: number;
  candidate_id?: number;
  need_id?: number | null;
  candidate?: { display_name: string; specialization: string | null; claimed_grade: string | null; verification_status: string; verified_grade: string | null; verified_sublevel: string | null } | null;
  company: string;
  role: string;
  description: string;
  salary_from: number;
  salary_to: number;
  salary_type: "GROSS" | "NET";
  work_format: string;
  message: string;
  status: string;
  contacts_unlocked?: boolean;
  contacts?: Contacts;
}
export interface CatalogSkill {
  code: string;
  name: string;
  verifiable: boolean;
}
export interface Catalog {
  specializations: { code: string; name: string; assessment_available: boolean }[];
  sublevel_labels: Record<string, string>;
  grades: Record<string, string[]>;
  skills: CatalogSkill[];
}
export interface Need {
  id: number;
  status?: "OPEN" | "CLOSED";
  public_to_candidates?: boolean;
  title: string;
  target_grade: string;
  target_sublevel: string | null;
  required_skills: { skill: string }[];
  optional_skills: { skill: string }[];
  salary_from: number;
  salary_to: number;
  salary_type: "GROSS" | "NET";
  work_formats: string[];
  location: string | null;
  description?: string | null;
}
