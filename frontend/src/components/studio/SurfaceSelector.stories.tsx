import type { Meta, StoryObj } from "@storybook/react";
import { SurfaceSelector } from "./SurfaceSelector";
import { regions, matchesByRegion } from "../../demoData";
import type { Surface } from "../../hooks/useSearchRun";

const surfaces: Surface[] = regions.map((region) => ({
  region,
  matchCount: matchesByRegion[region.id]?.length ?? 0,
  thumbUrl: matchesByRegion[region.id]?.[0]?.item.image_url ?? undefined,
}));

const meta: Meta<typeof SurfaceSelector> = {
  title: "Studio/SurfaceSelector",
  component: SurfaceSelector,
  args: { surfaces, selectedRegionId: regions[0].id, onSelect: () => {} },
};
export default meta;
type Story = StoryObj<typeof SurfaceSelector>;
export const Default: Story = {};
