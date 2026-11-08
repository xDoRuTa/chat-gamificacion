import DataLoader from 'dataloader';
import { getUserById, getGamificationProfile } from './upstream.js';

export function createLoaders() {
  return {
    // Loader de usuarios: agrupa IDs repetidas de autores en una misma consulta
    userLoader: new DataLoader(async (userIds) => {
      const users = await Promise.all(
        userIds.map(id => getUserById(id))
      );
      return users;
    }),

    // Loader de gamificación: agrupa consultas de nivel, XP y logros por usuario
    gamificationLoader: new DataLoader(async (userIds) => {
      const profiles = await Promise.all(
        userIds.map(id => getGamificationProfile(id))
      );
      return profiles;
    })
  };
}
