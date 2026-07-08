export type VoiceAiState =
  | 'listening'
  | 'transcribing'
  | 'reasoning'
  | 'speaking'
  | 'booking'
  | 'escalating'
  | 'ended';

export type VoiceEvent = {
  eventId: string;
  callId: string;
  type: 'state_changed' | 'transcript' | 'field_extracted' | 'booking' | 'handoff' | 'quality' | 'completed';
  occurredAt: string;
  payload: Record<string, unknown>;
};
