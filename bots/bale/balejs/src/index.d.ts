/// <reference types="node" />
export type ChatKind = "private" | "group" | "channel";
export interface BaleConfig { token?: string; session?: string; baseUrl?: string; wsUrl?: string; rpcUrl?: string; requestTimeoutMs?: number; maxRetries?: number; retryBaseDelayMs?: number; fetchImpl?: typeof fetch; logger?: Logger }
export interface Logger { debug(msg:string,meta?:unknown):void; info(msg:string,meta?:unknown):void; warn(msg:string,meta?:unknown):void; error(msg:string,meta?:unknown):void }
export interface Message { message_id?:number|string; text?:string; caption?:string; chat:{id:number|string;type?:string;title?:string;username?:string}; from?:{id:number|string;first_name?:string;username?:string}; date?:number; [key:string]:unknown }
export interface RetryPolicy { maxRetries:number; baseDelayMs:number; maxDelayMs:number }
export interface UserAdapter { request(method:string,payload?:Record<string,unknown>,context?:{session?:string}):Promise<unknown>; loginWithPhone?(phone:string,code:string,password?:string):Promise<string> }
export class BaleError extends Error { code?:string|number; status?:number; retryable:boolean; toJSON():{code?:string|number;message:string;status?:number;retryable?:boolean} }
export class BaleAuthError extends BaleError {}
export class BaleValidationError extends BaleError {}
export class BaleTransportError extends BaleError {}
export class HttpTransport { constructor(options?:Record<string,unknown>); request(url:string,options?:Record<string,unknown>):Promise<unknown> }
export class BotClient {
 constructor(options:{token:string;baseUrl?:string;timeoutMs?:number;maxRetries?:number;fetchImpl?:typeof fetch;logger?:Logger});
 call(method:string,payload?:Record<string,unknown>,options?:{signal?:AbortSignal}):Promise<any>;
 onMessage(fn:(message:Message,client:this)=>unknown):this;
 onCommand(command:string,fn:(message:Message,args:string[],client:this)=>unknown):this;
 onCallback(fn:(query:any,client:this)=>unknown):this;
 onPreCheckout(fn:(query:any,client:this)=>unknown):this;
 sendMessage(chatId:string|number,text:string,options?:Record<string,unknown>):Promise<any>;
 editMessage(chatId:string|number,messageId:string|number,text:string,options?:Record<string,unknown>):Promise<any>;
 deleteMessage(chatId:string|number,messageId:string|number):Promise<any>;
 forwardMessage(chatId:string|number,fromChatId:string|number,messageId:string|number):Promise<any>;
 copyMessage(chatId:string|number,fromChatId:string|number,messageId:string|number,options?:Record<string,unknown>):Promise<any>;
 sendPhoto(chatId:string|number,photo:string,options?:Record<string,unknown>):Promise<any>;
 sendDocument(chatId:string|number,document:string,options?:Record<string,unknown>):Promise<any>;
 sendInvoice(options:Record<string,unknown>):Promise<any>;
 answerPreCheckoutQuery(id:string,ok:boolean,errorMessage?:string):Promise<any>;
 answerCallbackQuery(id:string,options?:Record<string,unknown>):Promise<any>;
 setWebhook(url:string,options?:Record<string,unknown>):Promise<any>;
 deleteWebhook(options?:Record<string,unknown>):Promise<any>;
 getUpdates(options?:Record<string,unknown>):Promise<any[]>;
 handleUpdate(update:any):Promise<void>;
 polling(options?:{signal?:AbortSignal;timeout?:number;backoffMs?:number}):Promise<void>;
}
export class UserClient {
 constructor(options:{adapter:UserAdapter;session?:string;logger?:Logger});
 static loginWithPhone(options:{phone:string;adapter:UserAdapter;promptCode:()=>Promise<string>;promptPassword?:()=>Promise<string>;saveSession?:(session:string)=>Promise<void>;logger?:Logger}):Promise<UserClient>;
 onMessage(fn:(update:any,client:this)=>unknown):this;
 call(method:string,payload?:Record<string,unknown>):Promise<any>;
 sendMessage(chatId:string|number,text:string,options?:Record<string,unknown>):Promise<any>;
 editMessage(chatId:string|number,messageId:string|number,text:string):Promise<any>;
 deleteMessage(chatId:string|number,messageId:string|number):Promise<any>;
 forwardMessage(fromChatId:string|number,toChatId:string|number,messageId:string|number):Promise<any>;
 copyMessage(fromChatId:string|number,toChatId:string|number,messageId:string|number):Promise<any>;
 sendPhoto(chatId:string|number,file:string,options?:Record<string,unknown>):Promise<any>;
 sendDocument(chatId:string|number,file:string,options?:Record<string,unknown>):Promise<any>;
 joinChat(chatId:string|number):Promise<any>; leaveChat(chatId:string|number):Promise<any>; getChat(chatId:string|number):Promise<any>; getUpdates(options?:Record<string,unknown>):Promise<any[]>; poll(options?:{signal?:AbortSignal;intervalMs?:number}):Promise<void>
}
export class Bale { static bot(options:ConstructorParameters<typeof BotClient>[0]):BotClient; static user(options:ConstructorParameters<typeof UserClient>[0]):UserClient }
export function parseBaleLink(link:string):{isBot:boolean;target:string;messageId:number};
export function chunkText(text:string,max?:number):string[];
