/**
 * Curated recipe suggestions — shown on home page.
 * English: popular American/international favorites
 * Spanish/Ecuador: traditional Ecuadorian recipes
 */

export interface SuggestedRecipe {
  title: string;
  description: string;
  emoji: string;
  url: string;
  cuisine: string;
  time?: string;
}

const GENERAL_RECIPES: SuggestedRecipe[] = [
  { title: 'Classic Chicken Parmesan', description: 'Crispy breaded chicken with marinara and melted mozzarella', emoji: '🍗', url: 'https://www.seriouseats.com/the-best-chicken-parmesan-recipe', cuisine: 'Italian', time: '45 min' },
  { title: 'Beef Tacos', description: 'Seasoned ground beef with fresh toppings', emoji: '🌮', url: 'https://www.seriouseats.com/ground-beef-tacos-recipe', cuisine: 'Mexican', time: '25 min' },
  { title: 'Pasta Carbonara', description: 'Creamy egg and pancetta pasta — the Roman classic', emoji: '🍝', url: 'https://www.seriouseats.com/pasta-carbonara-sauce-recipe', cuisine: 'Italian', time: '25 min' },
  { title: 'Thai Basil Chicken', description: 'Quick stir-fry with holy basil and chili', emoji: '🐔', url: 'https://www.seriouseats.com/thai-style-chicken-with-basil-recipe', cuisine: 'Thai', time: '20 min' },
  { title: 'Sheet Pan Salmon', description: 'Roasted salmon with vegetables — one pan, easy cleanup', emoji: '🐟', url: 'https://www.seriouseats.com/sheet-pan-salmon-recipe', cuisine: 'American', time: '30 min' },
  { title: 'Butter Chicken', description: 'Rich and creamy Indian tomato-based curry', emoji: '🍛', url: 'https://www.seriouseats.com/indian-butter-chicken-recipe', cuisine: 'Indian', time: '50 min' },
  { title: 'Shakshuka', description: 'Eggs poached in spiced tomato sauce', emoji: '🍳', url: 'https://www.seriouseats.com/shakshuka-north-african-egg-dish-recipe', cuisine: 'Middle Eastern', time: '30 min' },
  { title: 'Classic Beef Stew', description: 'Hearty slow-cooked beef with root vegetables', emoji: '🥘', url: 'https://www.seriouseats.com/all-american-beef-stew-recipe', cuisine: 'American', time: '3 hrs' },
  { title: 'Pad Thai', description: 'Sweet, sour, salty rice noodle stir-fry', emoji: '🍜', url: 'https://www.seriouseats.com/pad-thai-recipe', cuisine: 'Thai', time: '30 min' },
  { title: 'Mushroom Risotto', description: 'Creamy Arborio rice with porcini mushrooms', emoji: '🍄', url: 'https://www.seriouseats.com/mushroom-risotto-recipe', cuisine: 'Italian', time: '40 min' },
  { title: 'Greek Lemon Chicken', description: 'Roasted chicken with lemon, oregano, and potatoes', emoji: '🍋', url: 'https://www.seriouseats.com/greek-style-roast-chicken-with-potatoes', cuisine: 'Greek', time: '1 hr' },
  { title: 'Fish Tacos', description: 'Beer-battered fish with cabbage slaw and crema', emoji: '🐠', url: 'https://www.seriouseats.com/fish-tacos-recipe', cuisine: 'Mexican', time: '30 min' },
  { title: 'Chicken Tikka Masala', description: 'Tender chicken in creamy spiced tomato sauce', emoji: '🍗', url: 'https://www.seriouseats.com/chicken-tikka-masala-recipe', cuisine: 'Indian', time: '1 hr' },
  { title: 'Crispy Tofu Stir-Fry', description: 'Crispy tofu with vegetables in garlic sauce', emoji: '🥦', url: 'https://www.seriouseats.com/crispy-tofu-stir-fry-recipe', cuisine: 'Asian', time: '25 min' },
  { title: 'French Onion Soup', description: 'Caramelized onion soup with melted Gruyère', emoji: '🧅', url: 'https://www.seriouseats.com/french-onion-soup-recipe', cuisine: 'French', time: '1.5 hrs' },
  { title: 'Pulled Pork', description: 'Smoky slow-cooked pork shoulder', emoji: '🐷', url: 'https://www.seriouseats.com/easy-oven-pulled-pork-recipe', cuisine: 'American', time: '4 hrs' },
];

const ECUADORIAN_RECIPES: SuggestedRecipe[] = [
  { title: 'Encebollado', description: 'Sopa de atún con yuca y cebolla encurtida — la cura ecuatoriana', emoji: '🐟', url: 'https://www.laylita.com/recipes/encebollado-de-pescado/', cuisine: 'Ecuatoriana', time: '1 hr' },
  { title: 'Llapingachos', description: 'Tortillas de papa rellenas de queso con salsa de maní', emoji: '🥔', url: 'https://www.laylita.com/recipes/llapingachos-ecuadorian-stuffed-potato-patties/', cuisine: 'Ecuatoriana', time: '45 min' },
  { title: 'Seco de Pollo', description: 'Estofado de pollo en salsa de cerveza y cilantro', emoji: '🍗', url: 'https://www.laylita.com/recipes/seco-de-pollo/', cuisine: 'Ecuatoriana', time: '1 hr' },
  { title: 'Locro de Papas', description: 'Sopa cremosa de papas con queso y aguacate', emoji: '🥣', url: 'https://www.laylita.com/recipes/locro-de-papas/', cuisine: 'Ecuatoriana', time: '45 min' },
  { title: 'Ceviche Ecuatoriano', description: 'Camarones en jugo de limón con tomate y cilantro', emoji: '🦐', url: 'https://www.laylita.com/recipes/shrimp-ceviche-ecuadorian/', cuisine: 'Ecuatoriana', time: '30 min' },
  { title: 'Bolón de Verde', description: 'Bolas de plátano verde con queso y chicharrón', emoji: '🟢', url: 'https://www.laylita.com/recipes/bolon-de-verde/', cuisine: 'Ecuatoriana', time: '30 min' },
  { title: 'Fritada', description: 'Cerdo frito cocido en su propia grasa con mote y llapingachos', emoji: '🐷', url: 'https://www.laylita.com/recipes/fritada-ecuadorian-braised-pork/', cuisine: 'Ecuatoriana', time: '2 hrs' },
  { title: 'Arroz con Menestra y Carne Asada', description: 'Arroz con frijoles guisados y carne a la parrilla', emoji: '🥩', url: 'https://www.laylita.com/recipes/arroz-con-menestra-y-carne-asada/', cuisine: 'Ecuatoriana', time: '1.5 hrs' },
  { title: 'Fanesca', description: 'Sopa tradicional de Semana Santa con granos y bacalao', emoji: '🫘', url: 'https://www.laylita.com/recipes/fanesca/', cuisine: 'Ecuatoriana', time: '3 hrs' },
  { title: 'Hornado', description: 'Cerdo horneado lentamente con especias ecuatorianas', emoji: '🍖', url: 'https://www.laylita.com/recipes/hornado-roasted-pork/', cuisine: 'Ecuatoriana', time: '4 hrs' },
  { title: 'Empanadas de Viento', description: 'Empanadas crujientes rellenas de queso con azúcar', emoji: '🥟', url: 'https://www.laylita.com/recipes/empanadas-de-viento/', cuisine: 'Ecuatoriana', time: '45 min' },
  { title: 'Tigrillo', description: 'Plátano verde majado con huevo y queso — desayuno costeño', emoji: '🍌', url: 'https://www.laylita.com/recipes/tigrillo/', cuisine: 'Ecuatoriana', time: '20 min' },
  { title: 'Seco de Chivo', description: 'Estofado de cabra en salsa de naranjilla y cerveza', emoji: '🐐', url: 'https://www.laylita.com/recipes/seco-de-chivo/', cuisine: 'Ecuatoriana', time: '2 hrs' },
  { title: 'Churrasco Ecuatoriano', description: 'Bistec con huevo frito, arroz, papas fritas y ensalada', emoji: '🥩', url: 'https://www.laylita.com/recipes/churrasco-ecuatoriano/', cuisine: 'Ecuatoriana', time: '30 min' },
  { title: 'Humitas', description: 'Tamales dulces de choclo tierno envueltos en hoja de maíz', emoji: '🌽', url: 'https://www.laylita.com/recipes/humitas-ecuadorian-fresh-corn-tamales/', cuisine: 'Ecuatoriana', time: '1.5 hrs' },
  { title: 'Caldo de Gallina', description: 'Sopa reconfortante de gallina criolla con papas', emoji: '🐓', url: 'https://www.laylita.com/recipes/caldo-de-gallina/', cuisine: 'Ecuatoriana', time: '2 hrs' },
];

/** Return N random recipes from the appropriate list */
export function getSuggestions(locale: 'en' | 'es', count: number = 4): SuggestedRecipe[] {
  const pool = locale === 'es' ? ECUADORIAN_RECIPES : GENERAL_RECIPES;
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
}
