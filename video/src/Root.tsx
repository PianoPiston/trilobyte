import { Composition } from "remotion";
import { Trilobyte, TOTAL } from "./Trilobyte";
export const Root = () => (
  <Composition id="Trilobyte" component={Trilobyte} durationInFrames={TOTAL} fps={30} width={1920} height={1080} />
);
