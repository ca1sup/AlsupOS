import { z } from 'zod';

// --- Primitives ---
export const HealthStatusSchema = z.object({
  ollama: z.enum(['checking', 'online', 'offline']),
  db: z.enum(['checking', 'online', 'offline']),
});
export type HealthStatus = z.infer<typeof HealthStatusSchema>;

export const JournalEntrySchema = z.object({
  date: z.string(),
  snippet: z.string(),
});
export type JournalEntry = z.infer<typeof JournalEntrySchema>;

// --- Chat ---
export const SourceSchema = z.object({
  file: z.string(),
  page: z.number().optional(),
  text: z.string(),
});
export type Source = z.infer<typeof SourceSchema>;

export const ChatMessageSchema = z.object({
  role: z.enum(['user', 'assistant']),
  content: z.string(),
  sources: z.array(SourceSchema).optional(),
  isTyping: z.boolean().optional(),
  isStreaming: z.boolean().optional(),
  persona: z.string().optional(),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

export const ChatSessionSchema = z.object({
  id: z.number(),
  name: z.string(),
  created_at: z.string(),
  last_updated: z.string().optional(),
});
export type ChatSession = z.infer<typeof ChatSessionSchema>;

// --- Dashboard ---
export const HealthMetricSchema = z.object({
  id: z.number(),
  date: z.string(),
  weight_kg: z.number().nullable(),
  active_calories: z.number().nullable(),
  source: z.string(),
  steps_count: z.number().nullable().optional(),
  sleep_total_duration: z.string().nullable().optional(),
  resting_hr: z.number().nullable().optional(),
  hrv_ms: z.number().nullable().optional(),
  vo2_max: z.number().nullable().optional(),
});
export type HealthMetric = z.infer<typeof HealthMetricSchema>;

export const FinanceCategorySchema = z.object({
  category: z.string(),
  budgeted: z.number(),
  spent: z.number(),
  remaining: z.number(),
  percent: z.number(),
});
export type FinanceCategory = z.infer<typeof FinanceCategorySchema>;

export const DashboardDataSchema = z.object({
  suggestions: z.any().nullable(),
  tasks: z.array(z.any()),
  events: z.array(z.any()),
  journals: z.array(JournalEntrySchema).default([]),
  memories: z.array(JournalEntrySchema).default([]),
  healthMetrics: z.array(HealthMetricSchema).default([]),
  finance: z.array(FinanceCategorySchema).default([]),
});
export type DashboardData = z.infer<typeof DashboardDataSchema>;

// --- Settings & System ---
export const PersonaSchema = z.object({
  name: z.string(),
  icon: z.string(),
  prompt: z.string(),
  default_folder: z.string().optional().default('all'), // Add this line
});
export type Persona = z.infer<typeof PersonaSchema>;

export const OllamaModelSchema = z.object({
  name: z.string(),
  size: z.number(),
  modified_at: z.string(),
});
export type OllamaModel = z.infer<typeof OllamaModelSchema>;

export const FileStatusSchema = z.object({
  name: z.string(),
  status: z.enum(['synced', 'modified', 'pending']),
});
export type FileStatus = z.infer<typeof FileStatusSchema>;