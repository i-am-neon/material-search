import type { Meta, StoryObj } from "@storybook/react";
import { MatchesGallery } from "./MatchesGallery";
import { matchesByRegion } from "../../demoData";

const meta: Meta<typeof MatchesGallery> = {
  title: "Studio/MatchesGallery",
  component: MatchesGallery,
  parameters: { layout: "fullscreen" },
  args: {
    surfaceLabel: "floor",
    matches: matchesByRegion["terrazzo-floor"].map((m, i) => ({ ...m, similarity: 0.96 - i * 0.05 })),
    cartIds: [],
    onToggleCart: () => {},
  },
  decorators: [(S) => <div style={{ padding: 32 }}><S /></div>],
};
export default meta;
type Story = StoryObj<typeof MatchesGallery>;
export const Default: Story = {};
