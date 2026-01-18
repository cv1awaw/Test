import { Chat, ChatOptions, ModelType, Site } from './base';
// import { Mcbbs } from './mcbbs';
// import { Phind } from './phind';
// import { Vita } from './vita';
// import { Copilot } from './copilot';
// import { Skailar } from './skailar';
// import { FakeOpen } from './fakeopen';
// import { EasyChat } from './easychat';
// import { Better } from './better';
// import { PWeb } from './pweb';
// import { Bai } from './bai';
// import { Gra } from './gra';
// import { Magic } from './magic';
// import { Chim } from './chim';
// import { Ram } from './ram';
// import { Chur } from './chur';
// import { Xun } from './xun';
// import { VVM } from './vvm';
// import { ClaudeChat } from './claude';
// import { Cursor } from './cursor';
// import { Auto } from './auto';
// import { ChatBase } from './chatbase';
// import { OpenPrompt } from './openprompt';
// import { AILS } from './ails';
// import { Perplexity } from './perplexity';
// import { ChatDemo } from './chatdemo';
// import { SinCode } from './sincode';
// import { OpenAI } from './openai';
// import { OneAPI } from './oneapi';
// import { Jasper } from './jasper';
// import { Pap } from './pap';
// import { MyShell } from './myshell';
// import { AcyToo } from './acytoo';
// import { Google } from './google';
// import { WWW } from './www';
import { DDG } from './ddg';
// import { Vanus } from './vanus';
// import { Mixer } from './mixer';
// import { Merlin } from './merlin';
// import { Airops } from './airops';
// import { Langdock } from './langdock';
// import { Toyy } from './toyy';
// import { TakeOff } from './takeoff';
// import { Navit } from './navit';
// import { ClaudeAPI } from './claudeapi';
// import { Stack } from './stack';
// import { TD } from './td';
// import { Izea } from './izea';
// import { Askx } from './askx';
// import { OpenSess } from './opensess';
// import { Hypotenuse } from './hypotenuse';
// import { Gemini } from './gemini';
// import { AIRoom } from './airoom';
// import { GPTGOD } from './gptgod';
// import { Midjourney } from './midjourney';
// import { FreeGPT4 } from './freegpt4';
// import { Domo } from './domo';
// import { BingCopilot } from './bingcopilot';
// import { Pika } from './pika';
// import { ClaudeAuto } from './claudeauto';
// import { Suno } from './suno';
// import { OpenAIAuto } from './openaiauto';
// import { FreeGPT35 } from './freegpt35';
// import { PerAuto } from './perauto';
// import { PerLabs } from './perlabs';
// import { MerlinGmail } from './merlingmail';
// import { Chatgateai } from './chatgateai';
// import { MJPlus } from './mjplus';
// import { Doc2x } from './doc2x';
// import { Bibi } from './bibi';
// import { Groq } from './groq';
// import { GLM } from './glm';
import { Config } from '../utils/config';
// import { Vidu } from './vidu';
// import { Flux } from './flux';
// import { Fireworks } from './fireworks';
// import { Runway } from './runway';
// import { MJWeb } from './mjweb';
// import { Ideogram } from './ideogram';

import { Pollinations } from './pollination';

export class ChatModelFactory {
  private readonly modelMap: Map<Site, Chat>;
  private readonly options: ChatOptions | undefined;

  constructor(options?: ChatOptions) {
    this.modelMap = new Map();
    this.options = options;
    this.init();
  }

  init() {
    // register new model here
    this.modelMap.set(Site.DDG, new DDG({ name: Site.DDG }));
    this.modelMap.set(Site.Pollinations, new Pollinations({ name: Site.Pollinations }));
  }

  get(model: Site): Chat | undefined {
    return this.modelMap.get(model);
  }

  forEach(callbackfn: (value: Chat, key: Site, map: Map<Site, Chat>) => void) {
    this.modelMap.forEach(callbackfn);
  }
}

export const chatModel = new ChatModelFactory();
