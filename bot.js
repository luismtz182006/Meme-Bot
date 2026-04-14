// ============================================
//   MEME BOT - Bot de Discord con IA + Memes
//   Requiere: discord.js, node-fetch, dotenv
//   npm install discord.js node-fetch dotenv
// ============================================

require('dotenv').config();
const { Client, GatewayIntentBits, Partials, EmbedBuilder, PermissionFlagsBits } = require('discord.js');
const fetch = (...args) => import('node-fetch').then(({ default: f }) => f(...args));
const fs = require('fs');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers,
  ],
  partials: [Partials.Message, Partials.Channel],
});

// ============================================
// PERSONALIDADES DEL BOT
// ============================================
const PERSONALITIES = {
  meme_lord: {
    name: '😂 Meme Lord',
    color: '#FFD700',
    emoji: '😂',
    system: `Eres un bot de Discord latino extremadamente gracioso y memero. 
    Respondes SIEMPRE en español latino con humor, slang y referencias a memes virales.
    Usas palabras como: "bro", "wey", "crack", "jaja", "lmao", "neta", "no manches", "chale".
    Tus respuestas son cortas, directas y SIEMPRE incluyen emojis de memes (😂🗿💀🤣👀🫡🤙).
    Si alguien dice algo tonto, lo trolas con amor. Eres el alma de la fiesta.
    Máximo 3 oraciones por respuesta. Siempre termina con un emoji relevante.`,
  },
  serio: {
    name: '🧊 Modo Serio',
    color: '#4A90E2',
    emoji: '🧊',
    system: `Eres un asistente de Discord profesional y educado.
    Respondes en español formal y claro. Sin memes, sin groserías.
    Eres útil, preciso y conciso. Máximo 4 oraciones.
    Solo usas emojis cuando es apropiado (✅ ❌ ℹ️).`,
  },
  sarcasmo: {
    name: '😒 Sarcástico',
    color: '#9B59B6',
    emoji: '😒',
    system: `Eres un bot Discord increíblemente sarcástico en español.
    Todo lo que dices tiene un tono de "qué obvio" o "wow, qué inteligente eres".
    Usas frases como "qué sorpresa...", "nunca lo hubiera imaginado 🙄", "genio del siglo".
    Eres pasivo-agresivo pero sin insultar. Emojis favoritos: 😒🙄💅😑🤌.
    Corto y sarcástico, máximo 2-3 oraciones.`,
  },
  chairo: {
    name: '🤓 El Nerd',
    color: '#2ECC71',
    emoji: '🤓',
    system: `Eres un bot nerd y curioso que sabe de todo.
    Respondes con datos curiosos, referencias a videojuegos, anime, ciencia y tecnología.
    Hablas en español con términos técnicos pero los explicas de forma divertida.
    Usas emojis de: 🤓📚🔬🎮⚡🧠. Entusiasta y muy detallado.`,
  },
  troll: {
    name: '👹 Troll Mode',
    color: '#E74C3C',
    emoji: '👹',
    system: `Eres un troll de Discord PERO con límites (no insultas ni eres cruel).
    Siempre das respuestas inesperadas, sin sentido o que no tienen nada que ver.
    Respondes preguntas con otras preguntas. Dices verdades incómodas.
    Usas mucho: 💀🗿😈👹🤡. En español, caótico pero gracioso.
    Ejemplo: si preguntan la hora, dices "el tiempo es una ilusión, bro 🗿"`,
  },
  abuelita: {
    name: '👵 Abuelita Mode',
    color: '#F39C12',
    emoji: '👵',
    system: `Eres una abuelita latina adorable en Discord.
    Llamas a todos "mijito/mijita", "corazón", "cielo".
    Comparas todo con "en mis tiempos..." y das consejos de vida no pedidos.
    Ofreces comida virtual constantemente. Usas emojis: 👵❤️🍲🌺😊.
    Respondes en español con mucho cariño aunque no entiendes los memes.`,
  },
};

// ============================================
// ESTADO DEL BOT POR SERVIDOR
// ============================================
const serverConfig = new Map(); // guildId -> { personality, history, enabled }

function getConfig(guildId) {
  if (!serverConfig.has(guildId)) {
    serverConfig.set(guildId, {
      personality: 'meme_lord',
      history: [],
      enabled: true,
      respondAll: false, // si true responde a todos, si false solo a menciones
    });
  }
  return serverConfig.get(guildId);
}

// ============================================
// MEME APIs (gratis, sin key)
// ============================================
const MEME_APIS = [
  'https://meme-api.com/gimme',
  'https://meme-api.com/gimme/memes_of_the_week',
  'https://meme-api.com/gimme/dankmemes',
  'https://meme-api.com/gimme/me_irl',
];

async function getMeme() {
  try {
    const api = MEME_APIS[Math.floor(Math.random() * MEME_APIS.length)];
    const res = await fetch(api);
    const data = await res.json();
    if (data.url && !data.nsfw) return data;
    return null;
  } catch {
    return null;
  }
}

// ============================================
// EMOJIS DE MEMES POR CONTEXTO
// ============================================
const MEME_EMOJIS = {
  laugh: ['😂', '🤣', '💀', '☠️', '😭'],
  sus: ['👀', '🤨', '🧐', '😶', '🗿'],
  based: ['🗿', '💪', '😎', '🔥', '⚡'],
  cringe: ['😬', '🤮', '💀', '😵', '🫣'],
  thinking: ['🤔', '🧠', '💭', '🤯', '😤'],
  win: ['🏆', '👑', '🎉', '✨', '🙌'],
  loss: ['😔', '💔', '😢', '🫠', '😮‍💨'],
  hype: ['🔥', '💥', '⚡', '🚀', '🎯'],
};

function getRandomEmojis(count = 2) {
  const keys = Object.keys(MEME_EMOJIS);
  const randomKey = keys[Math.floor(Math.random() * keys.length)];
  const emojis = MEME_EMOJIS[randomKey];
  return Array.from({ length: count }, () => emojis[Math.floor(Math.random() * emojis.length)]).join('');
}

// ============================================
// LLAMADA A CLAUDE API
// ============================================
async function askClaude(message, guildId) {
  const config = getConfig(guildId);
  const personality = PERSONALITIES[config.personality];

  // Mantener historial corto (últimos 10 mensajes)
  if (config.history.length > 20) {
    config.history = config.history.slice(-20);
  }

  config.history.push({ role: 'user', content: message });

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 300,
        system: personality.system,
        messages: config.history,
      }),
    });

    const data = await response.json();
    const reply = data.content?.[0]?.text || '...';

    config.history.push({ role: 'assistant', content: reply });
    return reply;
  } catch (err) {
    console.error('Error Claude API:', err);
    return `Error conectando con la IA ${getRandomEmojis(1)}`;
  }
}

// ============================================
// COMANDOS DE SLASH (/)
// ============================================
const { REST, Routes, SlashCommandBuilder } = require('discord.js');

const commands = [
  new SlashCommandBuilder()
    .setName('personalidad')
    .setDescription('Cambia la personalidad del bot')
    .addStringOption(opt =>
      opt.setName('modo')
        .setDescription('Elige la personalidad')
        .setRequired(true)
        .addChoices(
          { name: '😂 Meme Lord (default)', value: 'meme_lord' },
          { name: '🧊 Modo Serio', value: 'serio' },
          { name: '😒 Sarcástico', value: 'sarcasmo' },
          { name: '🤓 El Nerd', value: 'chairo' },
          { name: '👹 Troll Mode', value: 'troll' },
          { name: '👵 Abuelita Mode', value: 'abuelita' },
        )
    ),

  new SlashCommandBuilder()
    .setName('meme')
    .setDescription('Manda un meme random 😂'),

  new SlashCommandBuilder()
    .setName('estado')
    .setDescription('Ver la personalidad actual del bot'),

  new SlashCommandBuilder()
    .setName('activar')
    .setDescription('Activa/desactiva que el bot responda a todos los mensajes')
    .addBooleanOption(opt =>
      opt.setName('valor')
        .setDescription('true = responde a todo | false = solo menciones')
        .setRequired(true)
    ),

  new SlashCommandBuilder()
    .setName('limpiar')
    .setDescription('Limpia el historial de conversación del bot'),

  new SlashCommandBuilder()
    .setName('ayuda')
    .setDescription('Muestra todos los comandos disponibles'),
].map(cmd => cmd.toJSON());

// Registrar comandos
async function registerCommands() {
  const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
  try {
    console.log('📡 Registrando comandos slash...');
    await rest.put(Routes.applicationCommands(process.env.CLIENT_ID), { body: commands });
    console.log('✅ Comandos registrados correctamente');
  } catch (err) {
    console.error('Error registrando comandos:', err);
  }
}

// ============================================
// EVENTOS DEL BOT
// ============================================
client.once('ready', async () => {
  console.log(`\n🤖 Bot online como: ${client.user.tag}`);
  console.log(`📊 Servidores: ${client.guilds.cache.size}`);
  client.user.setActivity('🗿 siendo un meme', { type: 'PLAYING' });
  await registerCommands();
});

// --- MANEJO DE COMANDOS SLASH ---
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  const config = getConfig(interaction.guildId);
  const { commandName } = interaction;

  // Solo moderadores/admins pueden cambiar personalidad y activar
  const isAdmin = interaction.member.permissions.has(PermissionFlagsBits.ManageMessages);

  if (commandName === 'personalidad') {
    if (!isAdmin) {
      return interaction.reply({ content: '❌ Solo moderadores pueden cambiar mi personalidad 😤', ephemeral: true });
    }
    const modo = interaction.options.getString('modo');
    config.personality = modo;
    config.history = []; // resetear historial al cambiar personalidad
    const p = PERSONALITIES[modo];

    const embed = new EmbedBuilder()
      .setTitle(`${p.emoji} Personalidad cambiada`)
      .setDescription(`Ahora soy: **${p.name}**`)
      .setColor(p.color)
      .setFooter({ text: 'Historial limpiado automáticamente' });

    return interaction.reply({ embeds: [embed] });
  }

  if (commandName === 'meme') {
    await interaction.deferReply();
    const meme = await getMeme();

    if (!meme) {
      return interaction.editReply('No pude conseguir un meme 😔 Intenta de nuevo');
    }

    const embed = new EmbedBuilder()
      .setTitle(meme.title || 'Meme del momento 😂')
      .setImage(meme.url)
      .setColor(PERSONALITIES[config.personality].color)
      .setFooter({ text: `r/${meme.subreddit || 'memes'} • ${getRandomEmojis(3)}` });

    return interaction.editReply({ embeds: [embed] });
  }

  if (commandName === 'estado') {
    const p = PERSONALITIES[config.personality];
    const embed = new EmbedBuilder()
      .setTitle('📊 Estado del Bot')
      .addFields(
        { name: 'Personalidad actual', value: p.name, inline: true },
        { name: 'Responde a todos', value: config.enabled && config.respondAll ? '✅ Sí' : '❌ Solo menciones', inline: true },
        { name: 'Mensajes en memoria', value: `${config.history.length}`, inline: true },
      )
      .setColor(p.color);
    return interaction.reply({ embeds: [embed] });
  }

  if (commandName === 'activar') {
    if (!isAdmin) {
      return interaction.reply({ content: '❌ Solo moderadores pueden hacer esto', ephemeral: true });
    }
    const valor = interaction.options.getBoolean('valor');
    config.respondAll = valor;
    return interaction.reply(
      valor
        ? `✅ Ahora respondo a **todos** los mensajes ${getRandomEmojis(2)}`
        : `✅ Ahora solo respondo cuando me **mencionen** ${getRandomEmojis(1)}`
    );
  }

  if (commandName === 'limpiar') {
    if (!isAdmin) {
      return interaction.reply({ content: '❌ Solo moderadores pueden limpiar mi memoria', ephemeral: true });
    }
    config.history = [];
    return interaction.reply(`🧹 Historial limpiado ${getRandomEmojis(1)}`);
  }

  if (commandName === 'ayuda') {
    const embed = new EmbedBuilder()
      .setTitle('🤖 Comandos del Bot')
      .setColor(PERSONALITIES[config.personality].color)
      .addFields(
        { name: '💬 `/meme`', value: 'Manda un meme random' },
        { name: '📊 `/estado`', value: 'Ver personalidad actual' },
        { name: '🎭 `/personalidad`', value: 'Cambiar personalidad (solo mods)' },
        { name: '⚡ `/activar`', value: 'Responder a todos o solo menciones (solo mods)' },
        { name: '🧹 `/limpiar`', value: 'Limpiar historial de conversación (solo mods)' },
        { name: '💡 Mencionar al bot', value: '@Bot [mensaje] — Chatear con IA' },
      )
      .setFooter({ text: 'Personalidades: Meme Lord | Serio | Sarcástico | Nerd | Troll | Abuelita' });
    return interaction.reply({ embeds: [embed] });
  }
});

// --- MANEJO DE MENSAJES ---
client.on('messageCreate', async (message) => {
  if (message.author.bot) return;
  if (!message.guild) return;

  const config = getConfig(message.guildId);
  const botMentioned = message.mentions.has(client.user);
  const shouldRespond = config.respondAll || botMentioned;

  if (!shouldRespond) return;

  // Probabilidad de mandar meme (30%)
  const sendMeme = Math.random() < 0.3;

  // Limpiar el mensaje de la mención
  const cleanMsg = message.content
    .replace(/<@!?\d+>/g, '')
    .trim() || 'hola';

  await message.channel.sendTyping();

  try {
    // Obtener respuesta de IA
    const aiReply = await askClaude(cleanMsg, message.guildId);

    // Si toca meme, mandarlo también
    if (sendMeme) {
      const meme = await getMeme();
      if (meme) {
        const personality = PERSONALITIES[config.personality];
        const embed = new EmbedBuilder()
          .setImage(meme.url)
          .setColor(personality.color)
          .setFooter({ text: `${getRandomEmojis(3)}` });

        await message.reply({ content: aiReply, embeds: [embed] });
        return;
      }
    }

    await message.reply(aiReply);
  } catch (err) {
    console.error('Error en messageCreate:', err);
    await message.reply(`Algo salió mal 😔 ${getRandomEmojis(1)}`);
  }
});

// ============================================
// INICIAR BOT
// ============================================
client.login(process.env.DISCORD_TOKEN);
