import type { Meta, StoryObj } from "@storybook/react";
import { StudioScreen } from "./StudioScreen";
import { regions, matchesByRegion } from "../../demoData";
import type { Surface } from "../../hooks/useSearchRun";
import demoRoom from "../../assets/demo-room.png";

const surfaces: Surface[] = regions.map((region) => ({
  region,
  matchCount: matchesByRegion[region.id]?.length ?? 0,
  thumbUrl: matchesByRegion[region.id]?.[0]?.item.image_url ?? undefined,
}));

const meta: Meta<typeof StudioScreen> = {
  title: "Studio/StudioScreen",
  component: StudioScreen,
  parameters: { layout: "fullscreen" },
  args: {
    prompt: "a warm matte floor tile",
    previewUrl: demoRoom,
    imageWidth: 1536,
    imageHeight: 1024,
    surfaces,
    selectedRegion: regions[0],
    selectedRegionId: regions[0].id,
    selectedMatches: matchesByRegion[regions[0].id].map((m, i) => ({ ...m, similarity: 0.96 - i * 0.05 })),
    cartIds: [],
    cartItems: [],
    cartSurfaceCount: 0,
    onSelectRegion: () => {},
    onToggleCart: () => {},
    onNewSearch: () => {},
    onOrder: () => {},
  },
};
export default meta;
type Story = StoryObj<typeof StudioScreen>;
export const Default: Story = {};
