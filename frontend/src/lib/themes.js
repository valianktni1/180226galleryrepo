// Gallery visual theme presets
// Each theme defines light + dark mode colours, fonts, and accent styling

export const GALLERY_THEMES = {
  classic_gold: {
    id: 'classic_gold',
    name: 'Classic Gold',
    preview: { accent: '#D4AF37', bg: '#FDFCF8', text: '#1C1917' },
    headingFont: 'Cormorant Garamond, serif',
    bodyFont: 'Manrope, sans-serif',
    light: {
      bg: '#FDFCF8', bgAlt: '#F5F2EB', bgCard: 'white', bgInstructions: 'white',
      text: '#57534E', textSub: '#A8A29E', textMuted: '#78716C', headingColor: '#1C1917',
      border: '#F5F2EB', accent: '#D4AF37', accentHover: '#B8962E',
      cardShadow: '0 2px 12px rgba(0,0,0,0.06)', emptyBg: '#F5F2EB',
    },
    dark: {
      bg: '#1A1A1A', bgAlt: '#252525', bgCard: '#2A2A2A', bgInstructions: '#222222',
      text: '#E8E4DF', textSub: '#A8A29E', textMuted: '#78716C', headingColor: '#F5F2EB',
      border: '#333333', accent: '#D4AF37', accentHover: '#B8962E',
      cardShadow: '0 2px 12px rgba(0,0,0,0.3)', emptyBg: '#252525',
    },
  },

  modern_minimal: {
    id: 'modern_minimal',
    name: 'Modern Minimal',
    preview: { accent: '#1C1917', bg: '#FFFFFF', text: '#1C1917' },
    headingFont: 'Manrope, sans-serif',
    bodyFont: 'Manrope, sans-serif',
    light: {
      bg: '#FFFFFF', bgAlt: '#F7F7F7', bgCard: '#FFFFFF', bgInstructions: '#F7F7F7',
      text: '#525252', textSub: '#A3A3A3', textMuted: '#737373', headingColor: '#0A0A0A',
      border: '#E5E5E5', accent: '#0A0A0A', accentHover: '#262626',
      cardShadow: '0 1px 8px rgba(0,0,0,0.04)', emptyBg: '#F5F5F5',
    },
    dark: {
      bg: '#0A0A0A', bgAlt: '#171717', bgCard: '#1C1C1C', bgInstructions: '#141414',
      text: '#D4D4D4', textSub: '#737373', textMuted: '#525252', headingColor: '#FAFAFA',
      border: '#2A2A2A', accent: '#FAFAFA', accentHover: '#D4D4D4',
      cardShadow: '0 1px 8px rgba(0,0,0,0.4)', emptyBg: '#171717',
    },
  },

  dark_elegance: {
    id: 'dark_elegance',
    name: 'Dark Elegance',
    preview: { accent: '#C9A96E', bg: '#141218', text: '#E8E0D4' },
    headingFont: 'Cormorant Garamond, serif',
    bodyFont: 'Manrope, sans-serif',
    light: {
      bg: '#F8F6F1', bgAlt: '#EDE8DF', bgCard: '#FDFCF9', bgInstructions: '#F3EFE8',
      text: '#5C554A', textSub: '#9E9588', textMuted: '#7A7267', headingColor: '#2C2519',
      border: '#E4DDD2', accent: '#C9A96E', accentHover: '#B0913F',
      cardShadow: '0 2px 14px rgba(0,0,0,0.06)', emptyBg: '#EDE8DF',
    },
    dark: {
      bg: '#141218', bgAlt: '#1C1A20', bgCard: '#211F25', bgInstructions: '#1A181E',
      text: '#E8E0D4', textSub: '#8C8478', textMuted: '#6E665C', headingColor: '#F5EFE5',
      border: '#2D2A32', accent: '#C9A96E', accentHover: '#B0913F',
      cardShadow: '0 2px 14px rgba(0,0,0,0.4)', emptyBg: '#1C1A20',
    },
  },

  soft_romantic: {
    id: 'soft_romantic',
    name: 'Soft Romantic',
    preview: { accent: '#C77D8A', bg: '#FDF8F8', text: '#4A3036' },
    headingFont: 'Cormorant Garamond, serif',
    bodyFont: 'Manrope, sans-serif',
    light: {
      bg: '#FDF8F8', bgAlt: '#F8EDED', bgCard: '#FFFFFF', bgInstructions: '#FEF5F5',
      text: '#6B5258', textSub: '#B8979D', textMuted: '#8E7178', headingColor: '#4A3036',
      border: '#F2E0E3', accent: '#C77D8A', accentHover: '#A8606D',
      cardShadow: '0 2px 14px rgba(120,50,60,0.06)', emptyBg: '#F8EDED',
    },
    dark: {
      bg: '#1E1518', bgAlt: '#271C20', bgCard: '#2C2125', bgInstructions: '#241A1E',
      text: '#E8D5D9', textSub: '#8E7178', textMuted: '#6B5258', headingColor: '#F5E5E9',
      border: '#3A2D32', accent: '#C77D8A', accentHover: '#A8606D',
      cardShadow: '0 2px 14px rgba(0,0,0,0.35)', emptyBg: '#271C20',
    },
  },

  earthy_botanical: {
    id: 'earthy_botanical',
    name: 'Earthy Botanical',
    preview: { accent: '#6B8F71', bg: '#F9F7F3', text: '#2D3B2E' },
    headingFont: 'Cormorant Garamond, serif',
    bodyFont: 'Manrope, sans-serif',
    light: {
      bg: '#F9F7F3', bgAlt: '#EDE9E1', bgCard: '#FEFDFB', bgInstructions: '#F3F0EA',
      text: '#5A6B5C', textSub: '#94A396', textMuted: '#778A79', headingColor: '#2D3B2E',
      border: '#DDD8CE', accent: '#6B8F71', accentHover: '#537A59',
      cardShadow: '0 2px 14px rgba(40,70,40,0.06)', emptyBg: '#EDE9E1',
    },
    dark: {
      bg: '#171E18', bgAlt: '#1E261F', bgCard: '#222B23', bgInstructions: '#1C241D',
      text: '#D4DED6', textSub: '#778A79', textMuted: '#5A6B5C', headingColor: '#E8F0EA',
      border: '#2E382F', accent: '#6B8F71', accentHover: '#537A59',
      cardShadow: '0 2px 14px rgba(0,0,0,0.35)', emptyBg: '#1E261F',
    },
  },
};

export const getTheme = (themeId, isDark) => {
  const preset = GALLERY_THEMES[themeId] || GALLERY_THEMES.classic_gold;
  const colors = isDark ? preset.dark : preset.light;
  return {
    ...colors,
    headingFont: preset.headingFont,
    bodyFont: preset.bodyFont,
    borderGold: colors.accent, // backwards compat
  };
};

export const THEME_LIST = Object.values(GALLERY_THEMES);
