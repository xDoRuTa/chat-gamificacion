import { createSchema } from 'graphql-yoga';
import { getChannels, getChannelMessages } from './upstream.js';

export const schema = createSchema({
  typeDefs: /* GraphQL */ `
    type Achievement {
      code: String!
      name: String!
      description: String
      unlocked_at: String
    }

    type GamificationProfile {
      user_id: String!
      level: Int!
      xp: Int!
      achievements: [Achievement!]!
    }

    type User {
      id: ID!
      username: String
      displayName: String
      gamification: GamificationProfile
    }

    type Message {
      id: ID!
      channel_id: ID!
      content: String!
      created_at: String
      author: User
    }

    type Channel {
      id: ID!
      name: String!
      description: String
      messages(limit: Int): [Message!]!
    }

    type Query {
      channels: [Channel!]!
      channel(id: ID!): Channel
      user(id: ID!): User
      gamificationProfile(userId: ID!): GamificationProfile
    }
  `,

  resolvers: {
    Query: {
      channels: async () => await getChannels(),
      channel: async (_, { id }) => {
        const channels = await getChannels();
        return channels.find(c => c.id === id) || null;
      },
      user: async (_, { id }, { loaders }) => {
        return await loaders.userLoader.load(id);
      },
      gamificationProfile: async (_, { userId }, { loaders }) => {
        return await loaders.gamificationLoader.load(userId);
      }
    },

    Channel: {
      messages: async (channel, { limit = 20 }) => {
        return await getChannelMessages(channel.id, limit);
      }
    },

    Message: {
      author: async (message, _, { loaders }) => {
        if (!message.user_id) return null;
        return await loaders.userLoader.load(message.user_id);
      }
    },

    User: {
      gamification: async (user, _, { loaders }) => {
        if (!user.id) return null;
        return await loaders.gamificationLoader.load(user.id);
      }
    }
  }
});
