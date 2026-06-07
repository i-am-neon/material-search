import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { CatalogPage } from "./CatalogPage";

const meta: Meta<typeof CatalogPage> = {
  title: "Catalog/CatalogPage",
  component: CatalogPage,
  parameters: { layout: "fullscreen" },
  decorators: [(Story) => <MemoryRouter><Story /></MemoryRouter>],
};
export default meta;

type Story = StoryObj<typeof CatalogPage>;

export const CuratedCatalog: Story = {};
