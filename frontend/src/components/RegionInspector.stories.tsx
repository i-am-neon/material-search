import type { Meta, StoryObj } from "@storybook/react";
import { matchesByRegion, regions } from "../demoData";
import { RegionInspector } from "./RegionInspector";

const selectedRegion = regions[0];

const meta = {
  title: "Regions/Region Inspector",
  component: RegionInspector,
  args: {
    region: selectedRegion,
    matches: matchesByRegion[selectedRegion.id],
    cartIds: [],
    onToggleCart: () => undefined,
  },
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (Story) => (
      <main className="app-shell">
        <div style={{ maxWidth: 430, marginLeft: "auto" }}>
          <Story />
        </div>
      </main>
    ),
  ],
} satisfies Meta<typeof RegionInspector>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithCartItems: Story = {
  args: {
    cartIds: [matchesByRegion[selectedRegion.id][0].id, matchesByRegion[selectedRegion.id][1].id],
  },
};
