import { CalculateMetadataFunction, Composition, staticFile } from "remotion";
import { DadosEp, Ep02 } from "./ep02/Ep02";
import { DadosF, Fofoca } from "./fofoca/Fofoca";

type Props = { arquivo: string; dados?: DadosEp };

const calcular: CalculateMetadataFunction<Props> = async ({ props }) => {
  const dados: DadosEp = await (await fetch(staticFile(props.arquivo))).json();
  return { durationInFrames: Math.ceil((dados.duracaoMs / 1000) * 30), props: { ...props, dados } };
};

const Ep: React.FC<Props> = ({ dados }) => (dados ? <Ep02 dados={dados} /> : null);

type PropsF = { arquivo: string; dados?: DadosF };
const calcularF: CalculateMetadataFunction<PropsF> = async ({ props }) => {
  const dados: DadosF = await (await fetch(staticFile(props.arquivo))).json();
  return { durationInFrames: Math.ceil((dados.duracaoMs / 1000) * 30), props: { ...props, dados } };
};
const EpF: React.FC<PropsF> = ({ dados }) => (dados ? <Fofoca dados={dados} /> : null);

export const RemotionRoot: React.FC = () => {
  return (
    <>
    {["fofoca01-mudkip", "fofoca02-dragonite"].map((id) => (
      <Composition key={id} id={id} component={EpF} durationInFrames={900} fps={30} width={1080} height={1920}
        defaultProps={{ arquivo: `${id}.json` }} calculateMetadata={calcularF} />
    ))}
    <Composition
      id="Ep02Charizard"
      component={Ep}
      durationInFrames={900}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{ arquivo: "ep02.json" }}
      calculateMetadata={calcular}
    />
    </>
  );
};
