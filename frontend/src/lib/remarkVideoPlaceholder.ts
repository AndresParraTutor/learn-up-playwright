type MdastNode = {
  type: string;
  value?: string;
  children?: MdastNode[];
  data?: {
    hName?: string;
    hProperties?: Record<string, unknown>;
  };
};

const pattern = /^\[placeholder\]([\s\S]*?)\[\/placeholder\]$/;

export default function remarkVideoPlaceholder() {
  return (tree: MdastNode) => {
    function visit(node: MdastNode) {
      if (node.type === "paragraph" && node.children?.length === 1) {
        const child = node.children[0];
        const match =
          child.type === "text" && child.value ? pattern.exec(child.value) : null;
        if (match) {
          node.data = {
            hName: "div",
            hProperties: { className: ["video-placeholder"] },
          };
          node.children = [{ type: "text", value: match[1] }];
          return;
        }
      }
      node.children?.forEach(visit);
    }
    visit(tree);
  };
}
