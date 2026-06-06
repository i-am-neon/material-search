import type { Meta, StoryObj } from "@storybook/react";
import { SpecificationTray } from "./SpecificationTray";
import { matchesByRegion } from "../../demoData";

const meta: Meta<typeof SpecificationTray> = {
  title: "Studio/SpecificationTray",
  component: SpecificationTray,
  parameters: { layout: "fullscreen" },
  args: {
    items: [matchesByRegion["terrazzo-floor"][0], matchesByRegion["walnut-panels"][0], matchesByRegion["sage-fabric"][0]],
    surfaceCount: 3,
    onOrder: () => {},
  },
};
export default meta;
type Story = StoryObj<typeof SpecificationTray>;
export const Default: Story = {};
export const Empty: Story = { args: { items: [], surfaceCount: 0 } };
