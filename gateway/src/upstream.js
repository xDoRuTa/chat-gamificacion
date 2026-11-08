const BASE_USERS_URL = process.env.USERS_URL || 'http://user-service.servicios-base.svc.cluster.local:8000';
const BASE_CHANNELS_URL = process.env.CHANNELS_URL || 'http://channel-service.servicios-base.svc.cluster.local:8000';
const BASE_MESSAGES_URL = process.env.MESSAGES_URL || 'http://message-service.servicios-base.svc.cluster.local:8000';
const GAMIFICATION_URL = process.env.GAMIFICATION_URL || 'http://gamification-api.grupo-gamificacion.svc.cluster.local:8000';

async function fetchJSON(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);
  
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    clearTimeout(timeout);
    return null; // Retorna null si el servicio cae para permitir errores parciales
  }
}

export async function getChannels() {
  return await fetchJSON(`${BASE_CHANNELS_URL}/api/v1/channels`) || [];
}

export async function getChannelMessages(channelId, limit = 20) {
  const msgs = await fetchJSON(`${BASE_MESSAGES_URL}/api/v1/channels/${channelId}/messages`);
  if (!msgs) return [];
  return msgs.slice(0, limit);
}

export async function getUserById(userId) {
  return await fetchJSON(`${BASE_USERS_URL}/api/v1/users/${userId}`);
}

export async function getGamificationProfile(userId) {
  return await fetchJSON(`${GAMIFICATION_URL}/api/v1/users/${userId}/profile`);
}
