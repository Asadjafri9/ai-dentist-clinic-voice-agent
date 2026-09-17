export interface Business {
  id: string;
  name: string;
  slug: string;
  timezone: string;
  phone?: string;
  address?: string;
  business_hours: Record<string, { open: string; close: string; closed: boolean }>;
  greeting?: string;
  consent_disclosure?: string;
  faqs: { question: string; answer: string }[];
  assistant_name?: string;
  booking_horizon_days: number;
  slot_increment_minutes: number;
  booking_lead_time_minutes: number;
  transcript_retention_days: number;
  collect_email: boolean;
  vapi_assistant_id?: string | null;
  vapi_phone_number_id?: string | null;
  voice_sync: { status: string; last_synced_at?: string; error?: string | null; assistant_version?: string };
}

export interface Service {
  id: string;
  slug: string;
  display_name: string;
  description?: string | null;
  aliases: string[];
  duration_minutes: number;
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  active: boolean;
  voice_bookable: boolean;
  version: number;
}

export interface Provider {
  id: string;
  name: string;
  title?: string | null;
  service_ids: string[];
  active: boolean;
  version: number;
}

export interface Appointment {
  id: string;
  patient_id?: string;
  patient_name?: string;
  phone_suffix?: string;
  provider_id: string;
  service_id: string;
  call_id?: string;
  start_at: string;
  end_at: string;
  timezone?: string;
  status: string;
  source?: string;
  created_at?: string;
}

export interface CallRecord {
  id: string;
  vapi_call_id?: string;
  phone_suffix?: string;
  patient_id?: string;
  appointment_id?: string;
  started_at?: string;
  ended_at?: string;
  duration_seconds?: number;
  outcome: string;
  summary?: string;
  summary_status?: string;
  transcript_status?: string;
  transcript?: string;
  ended_reason?: string;
  created_at?: string;
}

export interface Patient {
  id: string;
  display_name?: string;
  phone?: string;
  phone_suffix?: string;
  email?: string;
  created_at?: string;
}

export interface DashboardSummary {
  date: string;
  timezone: string;
  calls_today: number;
  ai_booked_appointments: number;
  booking_rate: number | null;
  eligible_calls: number;
  upcoming: Appointment[];
}

export interface AvailabilityDay {
  local_date: string;
  providers: {
    provider_id: string;
    provider_name: string;
    windows: { start: string; end: string }[];
    booked: { id: string; start_at: string; end_at: string; service_id?: string; patient_name?: string }[];
  }[];
}
