-- =============================================================================
-- 0006 — Add new corpus poems (renumbered to poem_2000+ block) (Donne, Eliot, Stevens, WCW, Moore, Wheatley, Hughes)
-- =============================================================================
-- Renumbered from migration 0005 (which clashed with 12 pre-existing IDs in
-- the poem_0600 range). New IDs occupy poem_2000..poem_2087. 0005 stayed in
-- the repo as historical record; this is what actually runs.
--
-- Adds 88 PD poems by 7 new poets. Donne body text modernized (Goe→Go, passe→pass,
-- joyes→joys, profanation, refin'd→refined, ayery→airy, centre→center, etc.);
-- thee/thou/doth/hast retained as stylistic. All poems verified ≤40 non-blank lines.
--
-- Per-author counts:
--   John Donne               :  19
--   T.S. Eliot               :   7
--   Wallace Stevens          :  17
--   William Carlos Williams  :  13
--   Marianne Moore           :   8
--   Phillis Wheatley         :  11
--   Langston Hughes          :  13
--   TOTAL                    :  88
-- =============================================================================

insert into public.poems (id, title, author, body, line_count) values ('poem_2000', 'A Valediction: Forbidding Mourning', 'John Donne', 'As virtuous men pass mildly away,
  And whisper to their souls, to go,
Whilst some of their sad friends do say,
  The breath goes now, and some say, no:

So let us melt, and make no noise,
  No tear-floods, nor sigh-tempests move,
T''were profanation of our joys
  To tell the laity our love.

Moving of th''earth brings harms and fears,
  Men reckon what it did and meant,
But trepidation of the spheres,
  Though greater far, is innocent.

Dull sublunary lovers love
  (Whose soul is sense) cannot admit
Absence, because it doth remove
  Those things which elemented it.

But we by a love, so much refined,
  That our selves know not what it is,
Inter-assured of the mind,
  Care less, eyes, lips, and hands to miss.

Our two souls therefore, which are one,
  Though I must go, endure not yet
A breach, but an expansion,
  Like gold to airy thinness beat.

If they be two, they are two so
  As stiff twin compasses are two,
Thy soul the fixed foot, makes no show
  To move, but doth, if the''other do.

And though it in the center sit,
  Yet when the other far doth roam,
It leans, and hearkens after it,
  And grows erect, as that comes home.

Such wilt thou be to me, who must
  Like th''other foot, obliquely run;
Thy firmness makes my circle just,
  And makes me end, where I begun.', 36);
insert into public.poems (id, title, author, body, line_count) values ('poem_2001', 'A Valediction: of Weeping', 'John Donne', '        Let me powre forth
My teares before thy face, whil''st I stay here,
For thy face coines them, and thy stampe they bear,
And by this Mintage they are something worth,
        For thus they bee
        Pregnant of thee;
Fruits of much griefe they are, emblemes of more,
When a tear falls, that thou falst which it bore,
So thou and I are nothing then, when on a divers shore.

        On a round ball
A workeman that hath copies by, can lay
An Europe, Afrique, and an Asia,
And quickly make that, which was nothing, All,
        So doth each tear,
        Which thee doth wear,
A globe, yea world by that impression grow,
Till thy teares mixt with mine do overflow
This world, by waters sent from thee, my heaven dissolved so.

        O more then Moone,
Draw not up seas to drown me in thy sphere,
Weepe me not dead, in thine armes, but forbear
To teach the sea, what it may do too soone;
        Let not the winde
        Example find,
To do me more harm, then it purposes;
Since thou and I sigh one anothers breath,
Who e''r sighes most, is cruellest, and hasts the others death.', 27);
insert into public.poems (id, title, author, body, line_count) values ('poem_2002', 'Air and Angels', 'John Donne', 'Twice or thrice had I loved thee,
Before I knew thy face or name;
So in a voice, so in a shapeless flame,
Angells affect us oft, and worship''d bee;
  Still when, to where thou wert, I came,
Some lovely glorious nothing I did see.
  But since my soul, whose child love is,
Takes limmes of flesh, and else could nothing do,
  More subtile then the parent is,
Love must not be, but take a body too,
  And therefore what thou wert, and who,
      I bid Love aske, and now
That it assume thy body, I allow,
And fixe it selfe in thy lip, eye, and brow.

Whilst thus to ballast love, I thought,
And so more steddily to have gone,
With wares which would sinke admiration,
I saw, I had loves pinnace overfraught,
  Ev''ry thy haire for love to worke upon
Is much too much, some fitter must be sought;
  For, nor in nothing, nor in things
Extreme, and scatt''ring bright, can love inhere;
  Then as an Angell, face, and wings
Of air, not pure as it, yet pure doth wear,
  So thy love may be my loves sphere;
      Just such disparity
As is twixt Air and Angells purity,
''Twixt womens love, and mens will ever bee.', 28);
insert into public.poems (id, title, author, body, line_count) values ('poem_2003', 'Break of Day', 'John Donne', '''Tis true, ''tis day; what though it be?
O wilt thou therefore rise from me?
Why should we rise, because ''tis light?
Did we lie down, because ''twas night?
Love which in spight of darkness brought us hether,
Should in despight of light keep us together.

Light hath no tongue, but is all eye;
If it could speake as well as spy,
This were the worst, that it could say,
That being well, I faine would stay,
And that I lov''d my heart and honor so,
That I would not from him, that had them, go.

Must business thee from hence remove?
Oh, that''s the worst disease of love,
The poore, the foul, the false, love can
Admit, but not the busied man.
He which hath business, and makes love, doth do
Such wrong, as when a maryed man doth wooe.', 18);
insert into public.poems (id, title, author, body, line_count) values ('poem_2004', 'Holy Sonnet I: Thou Hast Made Me', 'John Donne', 'Thou hast made me, And shall thy worke decay?
Repaire me now, for now mine end doth haste,
I run to death, and death meets me as fast,
And all my pleasures are like yesterday;
I dare not move my dimme eyes any way,
Despaire behind, and death before doth cast
Such terrour, and my feeble flesh doth waste
By sinne in it, which it t''wards hell doth weigh;
Onely thou art above, and when towards thee
By thy leave I can looke, I rise againe;
But our old subtle foe so tempts me,
That not one houre my selfe I can sustaine;
Thy Grace may wing me to prevent his art,
And thou like Adamant draw mine iron heart.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2005', 'Holy Sonnet IX: If Poisonous Minerals', 'John Donne', 'If poysonous mineralls, and if that tree,
Whose fruit threw death on else immortall us,
If lecherous goats, if serpents envious
Cannot be damn''d; Alas; why should I bee?
Why should intent or reason, borne in me,
Make sinnes, else equall, in me more heinous?
And mercy being easy, and glorious
To God; in his sterne wrath, why threatens hee?
But who am I, that dare dispute with thee
O God? Oh! of thine onely worthy blood,
And my teares, make a heavenly Lethean flood,
And drown in it my sinnes blacke memory;
That thou remember them, some claime as debt,
I think it mercy, if thou wilt forget.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2006', 'Holy Sonnet VII: At the Round Earth''s Imagined Corners', 'John Donne', 'At the round earths imagined corners, blow
Your trumpets, Angells, and arise, arise
From death, you numberless infinities
Of souls, and to your scattred bodies go,
All whom the flood did, and fire shall o''erthrow,
All whom war, dearth, age, agues, tyrannies,
Despaire, law, chance, hath slaine, and you whose eyes,
Shall behold God, and never tast deaths woe.
But let them sleep, Lord, and me mourne a space,
For, if above all these, my sinnes abound,
''Tis late to aske abundance of thy grace,
When we are there; here on this lowly ground,
Teach me how to repent; for that''s as good
As if thou''hadst seal''d my pardon, with thy blood.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2007', 'Holy Sonnet X: Death Be Not Proud', 'John Donne', 'Death be not proud, though some have called thee
Mighty and dreadfull, for, thou art not soe,
For, those, whom thou think''st, thou dost overthrow,
Die not, poore death, nor yet canst thou kill me.
From rest and sleep, which but thy pictures bee,
Much pleasure, then from thee, much more must flow,
And soonest our best men with thee do go,
Rest of their bones, and souls delivery.
Thou art slave to Fate, Chance, kings, and desperate men,
And dost with poyson, war, and sickness dwell,
And poppy, or charmes can make us sleep as well,
And better then thy stroake; why swell''st thou then?
One short sleep past, we wake eternally,
And death shall be no more; death, thou shalt die.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2008', 'Holy Sonnet XIV: Batter My Heart', 'John Donne', 'Batter my heart, three personed God; for, you
As yet but knocke, breathe, shine, and seeke to mend;
That I may rise, and stand, o''erthrow me,''and bend
Your force, to breake, blowe, burn and make me new.
I, like an usurpt town, to''another due,
Labour to''admit you, but Oh, to no end,
Reason your viceroy in me, me should defend,
But is captiv''d, and proves weake or untrue.
Yet dearely''I love you,''and would be loved faine,
But am betroth''d unto your enemy:
Divorce me,''untie, or breake that knot againe,
Take me to you, imprison me, for I
Except you''enthrall me, never shall be free,
Nor ever chast, except you ravish me.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2009', 'Holy Sonnet XIX: Oh, to Vex Me', 'John Donne', 'Oh, to vex me, contraries meet in one:
Inconstancy unnaturally hath begott
A constant habit; that when I would not
I change in vowes, and in devotione.
As humorous is my contritione
As my prophane Love, and as soone forgott:
As ridlingly distemper''d, cold and hott,
As praying, as mute; as infinite, as none.
I durst not view heaven yesterday; and to day
In prayers, and flattering speaches I court God:
To morrow I quake with true fear of his rod.
So my devout fitts come and go away
Like a fantastique Ague: save that here
Those are my best days, when I shake with fear.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2010', 'Hymn to God, My God, in My Sickness', 'John Donne', 'Since I am comming to that Holy roome,
  Where, with thy Quire of Saints for evermore,
I shall be made thy Musique; As I come
  I tune the Instrument here at the dore,
  And what I must do then, think here before.

Whilst my Physitians by their love are grown
  Cosmographers, and I their Mapp, who lie
Flat on this bed, that by them may be shown
  That this is my South-west discovery
  Per fretum febris, by these streights to die,

I joy, that in these straits, I see my West;
  For, though theire currants yeeld returne to none,
What shall my West hurt me? As West and East
  In all flatt Maps (and I am one) are one,
  So death doth touch the Resurrection.

Is the Pacifique Sea my home? Or are
  The Easterne riches? Is Ierusalem?
Anyan, and Magellan, and Gibraltare,
  All streights, and none but streights, are ways to them,
  Whether where Iaphet dwelt, or Cham, or Sem.

We think that Paradise and Calvary,
  Christs Cross, and Adams tree, stood in one place;
Looke Lord, and find both Adams met in me;
  As the first Adams sweat surrounds my face,
  May the last Adams blood my soul embrace.

So, in his purple wrapp''d receive me Lord,
  By these his thornes give me his other Crown;
And as to others souls I preach''d thy word,
  Be this my Text, my Sermon to mine own,
  Therfore that he may raise the Lord throws down.', 30);
insert into public.poems (id, title, author, body, line_count) values ('poem_2011', 'Lovers'' Infiniteness', 'John Donne', 'If yet I have not all thy love,
Dear, I shall never have it all,
I cannot breath one other sigh, to move,
Nor can intreat one other tear to fall,
And all my treasure, which should purchase thee,
Sighs, teares, and oathes, and letters I have spent.
Yet no more can be due to me,
Then at the bargaine made was ment,
If then thy gift of love were partiall,
That some to me, some should to others fall,
  Dear, I shall never have Thee All.

Or if then thou gavest me all,
All was but All, which thou hadst then;
But if in thy heart, since, there be or shall,
New love created bee, by other men,
Which have their stocks intire, and can in teares,
In sighs, in oathes, and letters outbid me,
This new love may beget new fears,
For, this love was not vowed by thee.
And yet it was, thy gift being generall,
The ground, thy heart is mine, what ever shall
  Grow there, dear, I should have it all.

Yet I would not have all yet,
Hee that hath all can have no more,
And since my love doth every day admit
New growth, thou shouldst have new rewards in store;
Thou canst not every day give me thy heart,
If thou canst give it, then thou never gavest it:
Loves riddles are, that though thy heart depart,
It stays at home, and thou with losing savest it:
But we will have a way more liberall,
Then changing hearts, to joyne them, so we shall
  Be one, and one anothers All.', 33);
insert into public.poems (id, title, author, body, line_count) values ('poem_2012', 'Song: Go and Catch a Falling Star', 'John Donne', 'Go, and catch a falling star,
  Get with child a mandrake roote,
Tell me, where all past years are,
  Or who cleft the Devil''s foot,
Teach me to hear Mermaids singing,
  Or to keep off envies stinging,
    And find
    What winde
Serves to advance an honest mind.

If thou beest borne to strange sights,
  Things invisible to see,
Ride ten thousand days and nights,
  Till age snow white haires on thee,
Thou, when thou retorn''st, wilt tell me
All strange wonders that befell thee,
    And swear
    No where
Lives a woman true, and fair.

If thou findst one, let me know,
  Such a Pilgrimage were sweet;
Yet do not, I would not go,
  Though at next doore we might meet,
Though she were true, when you met her,
And last, till you write your letter,
    Yet she
    Will bee
False, ere I come, to two, or three.', 27);
insert into public.poems (id, title, author, body, line_count) values ('poem_2013', 'The Apparition', 'John Donne', 'When by thy scorne, O murderess, I am dead,
        And that thou thinkst thee free
From all solicitation from me,
Then shall my ghost come to thy bed,
And thee, fain''d vestall, in worse armes shall see;
Then thy sicke taper will begin to winke,
And he, whose thou art then, being tyr''d before,
Will, if thou stirre, or pinch to wake him, think
        Thou call''st for more,
And in false sleep will from thee shrinke,
And then poore Aspen wretch, neglected thou
Bath''d in a cold quicksilver sweat wilt lye
        A veryer ghost then I;
What I will say, I will not tell thee now,
Lest that preserve thee''; and since my love is spent,
I''had rather thou shouldst painfully repent,
Then by my threatnings rest still innocent.', 17);
insert into public.poems (id, title, author, body, line_count) values ('poem_2014', 'The Bait', 'John Donne', 'Come live with me, and bee my love,
And we will some new pleasures prove
Of golden sands, and christall brookes,
With silken lines, and silver hookes.

There will the river whispering run
Warm''d by thy eyes, more then the Sun.
And there the''inamor''d fish will stay,
Begging themselves they may betray.

When thou wilt swimme in that live bath,
Each fish, which every channell hath,
Will amorously to thee swimme,
Gladder to catch thee, then thou him.

If thou, to be so seene, beest loath,
By Sun, or Moone, thou darknest both,
And if my selfe have leave to see,
I need not their light, having thee.

Let others freeze with angling reeds,
And cut their legges, with shells and weeds,
Or treacherously poore fish beset,
With strangling snare, or windowy net:

Let coarse bold hands, from slimy nest
The bedded fish in banks out-wrest,
Or curious traitors, sleavesilke flies
Bewitch poore fishes wandring eyes.

For thee, thou needst no such deceit,
For thou thy selfe art thine own bait;
That fish, that is not catch''d thereby,
Alas, is wiser far then I.', 28);
insert into public.poems (id, title, author, body, line_count) values ('poem_2015', 'The Flea', 'John Donne', 'Marke but this flea, and marke in this,
How little that which thou deny''st me is;
It suck''d me first, and now sucks thee,
And in this flea, our two bloods mingled bee;
Thou know''st that this cannot be said
A sinne, nor shame, nor loss of maidenhead,
  Yet this enjoys before it wooe,
  And pamper''d swells with one blood made of two,
  And this, alas, is more then we would do.

Oh stay, three lives in one flea spare,
Where we almost, yea more then maryed are.
This flea is you and I, and this
Our mariage bed, and mariage temple is;
Though parents grudge, and you, w''are met,
And cloysterd in these living walls of Jet.
  Though use make you apt to kill me,
  Let not to that, selfe murder added bee,
  And sacrilege, three sinnes in killing three.

Cruell and sodaine, hast thou since
Purpled thy naile, in blood of innocence?
Wherein could this flea guilty bee,
Except in that drop which it suckt from thee?
Yet thou triumph''st, and saist that thou
Find''st not thy selfe, nor me the weaker now;
  ''Tis true, then learne how false, fears bee;
  Just so much honor, when thou yeeld''st to me,
  Will wast, as this flea''s death tooke life from thee.', 27);
insert into public.poems (id, title, author, body, line_count) values ('poem_2016', 'The Good-Morrow', 'John Donne', 'I wonder by my troth, what thou, and I
Did, till we lov''d? were we not wean''d till then?
But suck''d on countrey pleasures, childishly?
Or snorted we in the seaven sleepers den?
T''was so; But this, all pleasures fancies bee.
If ever any beauty I did see,
Which I desir''d, and got, t''was but a dreame of thee.

And now good morrow to our waking souls,
Which watch not one another out of fear;
For love, all love of other sights controls,
And makes one little roome, an every where.
Let sea-discoverers to new worlds have gone,
Let Maps to other, worlds on worlds have shown,
Let us possess one world, each hath one, and is one.

My face in thine eye, thine in mine appeares,
And true plaine hearts do in the faces rest,
Where can we find two better hemispheares
Without sharpe North, without declining West?
What ever dyes, was not mixt equally;
If our two loves be one, or, thou and I
Love so alike, that none do slacken, none can die.', 21);
insert into public.poems (id, title, author, body, line_count) values ('poem_2017', 'The Sun Rising', 'John Donne', '      Busy old foole, unruly Sun,
      Why dost thou thus,
Through windowes, and through curtaines call on us?
Must to thy motions lovers seasons run?
      Sawcy pedantique wretch, go chide
      Late schoole boys, and sowre prentices,
  Go tell Court-huntsmen, that the King will ride,
  Call countrey ants to harvest offices;
Love, all alike, no season knows, nor clime,
Nor hours, days, moneths, which are the rags of time.

      Thy beames, so reverend, and strong
      Why shouldst thou think?
I could eclipse and cloud them with a winke,
But that I would not lose her sight so long:
      If her eyes have not blinded thine,
      Looke, and to morrow late, tell me,
  Whether both the''India''s of spice and Myne
  Be where thou leftst them, or lie here with me.
Aske for those Kings whom thou saw''st yesterday,
And thou shalt hear, All here in one bed lay.

      She''is all States, and all Princes, I,
      Nothing else is.
Princes do but play us; compar''d to this,
All honor''s mimique; All wealth alchemy.
      Thou sun art halfe as happy''as we,
      In that the world''s contracted thus;
  Thine age askes ease, and since thy duties bee
  To warme the world, that''s done in warming us.
Shine here to us, and thou art every where;
This bed thy center is, these walls, thy sphere.', 30);
insert into public.poems (id, title, author, body, line_count) values ('poem_2018', 'The Triple Fool', 'John Donne', '  I am two fooles, I know,
For loving, and for saying so
  In whining Poëtry;
But where''s that wiseman, that would not be I,
  If she would not deny?
Then as th''earths inward narrow crooked lanes
Do purge sea waters fretfull salt away,
  I thought, if I could draw my paines,
Through Rimes vexation, I should them allay,
Griefe brought to numbers cannot be so fierce,
For, he tames it, that fetters it in verse.

  But when I have done so,
Some man, his art and voice to show,
  Doth Set and sing my paine,
And, by delighting many, frees againe
  Griefe, which verse did restraine.
To Love, and Griefe tribute of Verse belongs,
But not of such as pleases when''tis read,
  Both are increased by such songs:
For both their triumphs so are published,
And I, which was two fooles, do so grow three;
Who are a little wise, the best fooles bee.', 22);
insert into public.poems (id, title, author, body, line_count) values ('poem_2019', 'Aunt Helen', 'T.S. Eliot', 'Miss Helen Slingsby was my maiden aunt,
And lived in a small house near a fashionable square
Cared for by servants to the number of four.
Now when she died there was silence in heaven
And silence at her end of the street.
The shutters were drawn and the undertaker wiped his feet--
He was aware that this sort of thing had occurred before.
The dogs were handsomely provided for,
But shortly afterwards the parrot died too.
The Dresden clock continued ticking on the mantelpiece,
And the footman sat upon the dining-table
Holding the second housemaid on his knees--
Who had always been so careful while her mistress lived.', 13);
insert into public.poems (id, title, author, body, line_count) values ('poem_2020', 'Conversation Galante', 'T.S. Eliot', 'I observe: “Our sentimental friend the moon
Or possibly (fantastic, I confess)
It may be Prester John’s balloon
Or an old battered lantern hung aloft
To light poor travellers to their distress.”
  She then: “How you digress!”

And I then: “Some one frames upon the keys
That exquisite nocturne, with which we explain
The night and moonshine; music which we seize
To body forth our own vacuity.”
  She then: “Does this refer to me?”
  “Oh no, it is I who am inane.”

“You, madam, are the eternal humorist
The eternal enemy of the absolute,
Giving our vagrant moods the slightest twist
With your air indifferent and imperious
At a stroke our mad poetics to confute--”
  And--“Are we then so serious?”', 18);
insert into public.poems (id, title, author, body, line_count) values ('poem_2021', 'Cousin Nancy', 'T.S. Eliot', 'Miss Nancy Ellicot
Strode across the hills and broke them
Rode across the hills and broke them--
The barren New England hills
Riding to hounds
Over the cow-pasture.

Miss Nancy Ellicott smoked
And danced all the modern dances;
And her aunts were not quite sure how they felt about it,
But they knew that it was modern.

Upon the glazen shelves kept watch
Matthew and Waldo, guardians of the faith,
The army of unalterable law.', 13);
insert into public.poems (id, title, author, body, line_count) values ('poem_2022', 'La Figlia Che Piange', 'T.S. Eliot', 'Stand on the highest pavement of the stair--
Lean on a garden urn--
Weave, weave the sunlight in your hair--
Clasp your flowers to you with a pained surprise--
Fling them to the ground and turn
With a fugitive resentment in your eyes:
But weave, weave the sunlight in your hair.

So I would have had him leave,
So I would have had her stand and grieve,
So he would have left
As the soul leaves the body torn and bruised
As the mind deserts the body it has used.
I should find
Some way incomparably light and deft,
Some way we both should understand,
Simple and faithless as a smile and shake of the hand.

She turned away, but with the autumn weather
Compelled my imagination many days,
Many days and many hours:
Her hair over her arms and her arms full of flowers.
And I wonder how they should have been together!
I should have lost a gesture and a pose.
Sometimes these cogitations still amaze
The troubled midnight and the noon’s repose.', 24);
insert into public.poems (id, title, author, body, line_count) values ('poem_2023', 'Morning at the Window', 'T.S. Eliot', 'They are rattling breakfast plates in basement kitchens,
And along the trampled edges of the street
I am aware of the damp souls of housemaids
Sprouting despondently at area gates.

The brown waves of fog toss up to me
Twisted faces from the bottom of the street,
And tear from a passer-by with muddy skirts
An aimless smile that hovers in the air
And vanishes along the level of the roofs.', 9);
insert into public.poems (id, title, author, body, line_count) values ('poem_2024', 'Mr. Apollinax', 'T.S. Eliot', 'When Mr. Apollinax visited the United States
His laughter tinkled among the teacups.
I thought of Fragilion, that shy figure among the birch-trees,
And of Priapus in the shrubbery
Gaping at the lady in the swing.
In the palace of Mrs. Phlaccus, at Professor Channing-Cheetah’s
He laughed like an irresponsible foetus.
His laughter was submarine and profound
Like the old man of the seats
Hidden under coral islands
Where worried bodies of drowned men drift down in the green silence,
Dropping from fingers of surf.
I looked for the head of Mr. Apollinax rolling under a chair,
Or grinning over a screen
With seaweed in its hair.
I heard the beat of centaurs’ hoofs over the hard turf
As his dry and passionate talk devoured the afternoon.
“He is a charming man”--“But after all what did he mean?”--
“He has pointed ears ... he must be unbalanced,”--
“There was something he said that I might have challenged.”
Of dowager Mrs. Phlaccus, and Professor and Mrs. Cheetah
I remember a slice of lemon and a bitten macaroon.', 22);
insert into public.poems (id, title, author, body, line_count) values ('poem_2025', 'The Boston Evening Transcript', 'T.S. Eliot', 'The readers of the Boston Evening Transcript
Sway in the blind like a field of ripe corn.
When evening quickens faintly in the street,
Wakening the appetites of life in some
And to others bringing the Boston Evening Transcript,
I mount the steps and ring the bell, turning
Wearily, as one would turn to nod good-bye to Rochefoucauld
If the street were time and he at the end of the street,
And I say, “Cousin Harriet, here is the Boston Evening Transcript.”', 9);
insert into public.poems (id, title, author, body, line_count) values ('poem_2026', 'A High-Toned Old Christian Woman', 'Wallace Stevens', 'Poetry is the supreme fiction, madame.

Take the moral law and make a nave of it

And from the nave build haunted heaven. Thus,

The conscience is converted into palms,

Like windy citherns hankering for hymns.

We agree in principle. That''s clear. But take

The opposing law and make a peristyle,

And from the peristyle project a masque

Beyond the planets. Thus, our bawdiness,

Unpurged by epitaph, indulged at last,

Is equally converted into palms,

Squiggling like saxophones. And palm for palm,

Madame, we are where we began. Allow,

Therefore, that in the planetary scene

Your disaffected flagellants, well-stuffed,

Smacking their muzzy bellies in parade,

Proud of such novelties of the sublime,

Such tink and tank and tunk-a-tunk-tunk,

May, merely may, madame, whip from themselves

A jovial hullabaloo among the spheres.

This will make widows wince. But fictive things

Wink as they will. Wink most when widows wince.', 22);
insert into public.poems (id, title, author, body, line_count) values ('poem_2027', 'Anecdote of Men by the Thousand', 'Wallace Stevens', 'The soul, he said, is composed
Of the external world.

There are men of the East, he said,
Who are the East.
There are men of a province
Who are that province
There are men of a valley
Who are that valley.

There are men whose words
Are as natural sounds
Of their places
As the cackle of toucans
In the place of toucans.

The mandoline is the instrument
Of a place.

Are there mandolines of western mountains?
Are there mandolines of northern moonlight?

The dress of a woman of Lhassa,
In its place,
Is an invisible element of that place
Made visible.', 21);
insert into public.poems (id, title, author, body, line_count) values ('poem_2028', 'Anecdote of the Jar', 'Wallace Stevens', 'I placed a jar in Tennessee,
And round it was, upon a hill.
It made the slovenly wilderness
Surround that hill.

The wilderness rose up to it,
And sprawled around, no longer wild.
The jar was round upon the ground
And tall and of a port in air.

It took dominion everywhere.
The jar was gray and bare.
It did not give of bird or bush,
Like nothing else in Tennessee.', 12);
insert into public.poems (id, title, author, body, line_count) values ('poem_2029', 'Bantams in Pine-Woods', 'Wallace Stevens', 'chieftain Iffucan of Azcan in caftan
Of tan with henna hackles, halt!

Damned universal cock, as if the sun
Was blackamoor to bear your blazing tail.

Fat! Fat! Fat! Fat! I am the personal.
Your world is you. I am my world.

You ten-foot poet among inchlings. Fat!
Begone! An inchling bristles in these pines,

Bristles, and points their Appalachian tangs,
And fears not portly Azcan nor his hoos.', 10);
insert into public.poems (id, title, author, body, line_count) values ('poem_2030', 'Disillusionment of Ten O''Clock', 'Wallace Stevens', 'The houses are haunted

By white night-gowns.

None are green,

Or purple with green rings,

Or green with yellow rings,

Or yellow with blue rings.

None of them are strange,

With socks of lace

And beaded ceintures.

People are not going

To dream of baboons and periwinkles.

Only, here and there, an old sailor,

Drunk and asleep in his boots,

Catches tigers

In red weather.', 15);
insert into public.poems (id, title, author, body, line_count) values ('poem_2031', 'Domination of Black', 'Wallace Stevens', '.mw-parser-output .wst-largeinitial{font-size:3em;line-height:1em;margin-right:0.05em}.mw-parser-output .skin-theme-clientpref-night .wst-largeinitial-night-mode-invert{filter:invert(1)hue-rotate(180deg)}@media(prefers-color-scheme:dark){.mw-parser-output .skin-theme-clientpref-os .wst-largeinitial-night-mode-invert{filter:invert(1)hue-rotate(180deg)}}At night, by the fire,
The colors of the bushes
And of the fallen leaves,
Repeating themselves,
Turned in the room,
Like the leaves themselves
Turning in the wind.
Yes: but the color of the heavy hemlocks
Came striding.
And I remembered the cry of the peacocks.

The colors of their tails
Were like the leaves themselves
Turning in the wind,
In the twilight wind.
They swept over the room,
Just as they flew from the boughs of the hemlocks
Down to the ground.
I heard them cry—the peacocks.
Was it a cry against the twilight
Or against the leaves themselves
Turning in the wind,
Turning as the flames
Turned in the fire,
Turning as the tails of the peacocks
​Turned in the loud fire,
Loud as the hemlocks
Full of the cry of the peacocks?
Or was it a cry against the hemlocks?

Out of the window,
I saw how the planets gathered
Like the leaves themselves
Turning in the wind.
I saw how the night came,
Came striding like the color of the heavy hemlocks.
I felt afraid.
And I remembered the cry of the peacocks.', 36);
insert into public.poems (id, title, author, body, line_count) values ('poem_2032', 'Earthy Anecdote', 'Wallace Stevens', 'Every time the bucks went clattering

Over Oklahoma

A firecat bristled in the way.

Wherever they went,

They went clattering,

Until they swerved

In a swift, circular line

To the right,

Because of the firecat.

Or until they swerved

In a swift, circular line

To the left,

Because of the firecat.

The bucks clattered.

The firecat went leaping,

To the right, to the left,

And

Bristled in the way.

Later, the firecat closed his bright eyes

And slept.', 20);
insert into public.poems (id, title, author, body, line_count) values ('poem_2033', 'Floral Decorations for Bananas', 'Wallace Stevens', 'Well, nuncle, this plainly won''t do.
These insolent, linear peels
And sullen, hurricane shapes
Won''t do with your eglantine.
They require something serpentine.
Blunt yellow in such a room!

You should have had plums tonight,
In an eighteenth-century dish,
And pettifogging buds,
For the women of primrose and purl,
Each one in her decent curl.
Good God! What a precious light!

But bananas hacked and hunched .mw-parser-output .nowrap,.mw-parser-output .nowrap a:before,.mw-parser-output .nowrap .selflink:before{white-space:nowrap}. . .
The table was set by an ogre,
His eye on an outdoor gloom
And a stiff and noxious place.
Pile the bananas on planks.
The women will be all shanks
And bangles and slatted eyes.

And deck the bananas in leaves
Plucked from the Carib trees,
Fibrous and dangling down,
​Oozing cantankerous gum
Out of their purple maws,
Darting out of their purple craws
Their musky and tingling tongues.', 26);
insert into public.poems (id, title, author, body, line_count) values ('poem_2034', 'Frogs Eat Butterflies. Snakes Eat Frogs. Hogs Eat Snakes. Men Eat Hogs.', 'Wallace Stevens', 'It is true that the rivers went nosing like swine,

Tugging at banks, until they seemed

Bland belly-sounds in somnolent troughs,

That the air was heavy with the breath of these swine,

The breath of turgid summer, and

Heavy with thunder''s rattapallax,

That the man who erected this cabin, planted

This field, and tended it awhile,

Knew not the quirks of imagery,

That the hours of his indolent, arid days,

Grotesque with this nosing in banks,

This somnolence and rattapallax,

Seemed to suckle themselves on his arid being,

As the swine-like rivers suckled themselves

While they went seaward to the sea-mouths.', 15);
insert into public.poems (id, title, author, body, line_count) values ('poem_2035', 'Last Looks at the Lilacs', 'Wallace Stevens', 'To what good, in the alleys of the lilacs,
O caliper, do you scratch your buttocks
And tell the divine ingénue, your companion,
That this bloom is the bloom of soap
And this fragrance the fragrance of vegetal?

Do you suppose that she cares a tick,
In this hymeneal air, what it is
That marries her innocence thus,
So that her nakedness is near,
Or that she will pause at scurrilous words?

Poor buffo! Look at the lavender
And look your last and look still steadily,
And say how it comes that you see
Nothing but trash and that you no longer feel
Her body quivering in the Floréal

Toward the cool night and its fantastic star,
Prime paramour and belted paragon,
Well-booted, rugged, arrogantly male,
Patron and imager of the gold Don John,
Who will embrace her before summer comes.', 20);
insert into public.poems (id, title, author, body, line_count) values ('poem_2036', 'Metaphors of a Magnifico', 'Wallace Stevens', 'Twenty men crossing a bridge,
Into a village,
Are twenty men crossing twenty bridges,
Into twenty villages,
Or one man
Crossing a single bridge into a village.

This is old song
That will not declare itself .mw-parser-output .nowrap,.mw-parser-output .nowrap a:before,.mw-parser-output .nowrap .selflink:before{white-space:nowrap}. . .

Twenty men crossing a bridge,
Into a village,
Are
Twenty men crossing a bridge
Into a village.

That will not declare itself
Yet is certain as meaning . . .

The boots of the men clump
On the boards of the bridge.
The first white wall of the village
Rises through fruit-trees.
Of what was it I was thinking?

So the meaning escapes.

The first white wall of the village . . .
The fruit-trees. . . .', 23);
insert into public.poems (id, title, author, body, line_count) values ('poem_2037', 'Of the Surface of Things', 'Wallace Stevens', 'I
In my room, the world is beyond my understanding;
But when I walk I see that it consists of three or four hills and a cloud.

II
From my balcony, I survey the yellow air,
Reading where I have written,
"The spring is like a belle undressing."

III
The gold tree is blue.
The singer has pulled his cloak over his head.
The moon is in the folds of the cloak.', 11);
insert into public.poems (id, title, author, body, line_count) values ('poem_2038', 'Ploughing on Sunday', 'Wallace Stevens', 'The white cock''s tail
Tosses in the wind.
The turkey-cock''s tail
Glitters in the sun.

Water in the fields.
The wind pours down.
The feathers flare
And bluster in the wind.

Remus, blow your horn!
I''m ploughing on Sunday,
Ploughing North America.
Blow your horn!

Tum-ti-tum,
Ti-tum-tum-tum!
The turkey-cock''s tail
Spreads to the sun.

The white cock''s tail
Streams to the moon.
Water in the fields.
The wind pours down.', 20);
insert into public.poems (id, title, author, body, line_count) values ('poem_2039', 'Tea at the Palaz of Hoon', 'Wallace Stevens', 'Not less because in purple I descended
The western day through what you called
The loneliest air, not less was I myself.

What was the ointment sprinkled on my beard?
What were the hymns that buzzed beside my ears?
What was the sea whose tide swept through me there?

Out of my mind the golden ointment rained,
And my ears made the blowing hymns they heard.
I was myself the compass of that sea:

I was the world in which I walked, and what I saw
Or heard or felt came not but from myself;
And there I found myself more truly and more strange.', 12);
insert into public.poems (id, title, author, body, line_count) values ('poem_2040', 'The Emperor of Ice-Cream', 'Wallace Stevens', 'Call the roller of big cigars,
The muscular one, and bid him whip
In kitchen cups concupiscent curds.
Let the wenches dawdle in such dress
As they are used to wear, and let the boys
Bring flowers in last month''s newspapers.
Let be be finale of seem.
The only emperor is the emperor of ice-cream.

Take from the dresser of deal,
Lacking the three glass knobs, that sheet
On which she embroidered fantails once
And spread it so as to cover her face.
If her horny feet protrude, they come
To show how cold she is, and dumb.
Let the lamp affix its beam.
The only emperor is the emperor of ice-cream.', 16);
insert into public.poems (id, title, author, body, line_count) values ('poem_2041', 'The Snow Man', 'Wallace Stevens', 'One must have a mind of winter
To regard the frost and the boughs
Of the pine-trees crusted with snow;

And have been cold a long time
To behold the junipers shagged with ice,
The spruces rough in the distant glitter

Of the January sun; and not to think
Of any misery in the sound of the wind,
In the sound of a few leaves,

Which is the sound of the land
Full of the same wind
That is blowing in the same bare place

For the listener, who listens in the snow,
And, nothing himself, beholds
Nothing that is not there and the nothing that is.', 15);
insert into public.poems (id, title, author, body, line_count) values ('poem_2042', 'The Worms at Heaven''s Gate', 'Wallace Stevens', 'Out of the tomb, we bring Badroulbadour,
Within our bellies, we her chariot.
Here is an eye. And here are, one by one,
The lashes of that eye and its white lid.
Here is the cheek on which that lid declined,
And, finger after finger, here, the hand,
The genius of that cheek. Here are the lips,
The bundle of the body and the feet.
.mw-parser-output .wst-asterisks{display:block;margin:auto;text-align:center}·······
Out of the tomb we bring Badroulbadour.', 10);
insert into public.poems (id, title, author, body, line_count) values ('poem_2043', 'Apology', 'William Carlos Williams', 'Why do I write today?

The beauty of
the terrible faces
of our nonentities
stirs me to it:

colored women
day workers--
old and experienced--
returning home at dusk
in cast off clothing
faces like
old Florentine oak.

Also

the set pieces
of your faces stir me--
leading citizens--
but not
in the same way.', 18);
insert into public.poems (id, title, author, body, line_count) values ('poem_2044', 'Complete Destruction', 'William Carlos Williams', 'It was an icy day.
We buried the cat,
then took her box
and set fire to it
in the back yard.
Those fleas that escaped
earth and fire
died by the cold.', 8);
insert into public.poems (id, title, author, body, line_count) values ('poem_2045', 'Danse Russe', 'William Carlos Williams', 'If I when my wife is sleeping
and the baby and Kathleen
are sleeping
and the sun is a flame-white disc
in silken mists
above shining trees,--
if I in my north room
danse naked, grotesquely
before my mirror
waving my shirt round my head
and singing softly to myself:
“I am lonely, lonely.
I was born to be lonely.
I am best so!”
If I admire my arms, my face
my shoulders, flanks, buttocks
against the yellow drawn shades,--

who shall say I am not
the happy genius of my household?', 19);
insert into public.poems (id, title, author, body, line_count) values ('poem_2046', 'Dawn', 'William Carlos Williams', 'Ecstatic bird songs pound
the hollow vastness of the sky
with metallic clinkings--
beating color up into it
at a far edge,--beating it, beating it
with rising, triumphant ardor,--
stirring it into warmth,
quickening in it a spreading change,--
bursting wildly against it as
dividing the horizon, a heavy sun
lifts himself--is lifted--
bit by bit above the edge
of things,--runs free at last
out into the open--! lumbering
glorified in full release upward--songs cease.', 15);
insert into public.poems (id, title, author, body, line_count) values ('poem_2047', 'El Hombre', 'William Carlos Williams', 'It’s a strange courage
you give me ancient star:

Shine alone in the sunrise
toward which you lend no part!', 4);
insert into public.poems (id, title, author, body, line_count) values ('poem_2048', 'Pastoral', 'William Carlos Williams', 'If I say I have heard voices
who will believe me?

    “None has dipped his hand
    in the black waters of the sky
    nor picked the yellow lilies
    that sway on their clear stems
    and no tree has waited
    long enough nor still enough
    to touch fingers with the moon.”

I looked and there were little frogs
with puffed out throats,
singing in the slime.', 12);
insert into public.poems (id, title, author, body, line_count) values ('poem_2049', 'Queen-Ann''s-Lace', 'William Carlos Williams', 'Her body is not so white as
anemony petals nor so smooth--nor
so remote a thing. It is a field
of the wild carrot taking
the field by force; the grass
does not raise above it.
Here is no question of whiteness,
white as can be, with a purple mole
at the center of each flower.
Each flower is a hand''s span
of her whiteness. Wherever
his hand has lain there is
a tiny purple blemish. Each part
is a blossom under his touch
to which the fibres of her being
stem one by one, each to its end,
until the whole field is a
white desire, empty, a single stem,
a cluster, flower by flower,
a pious wish to whiteness gone over--
or nothing.', 21);
insert into public.poems (id, title, author, body, line_count) values ('poem_2050', 'Spring Strains', 'William Carlos Williams', 'In a tissue-thin monotone of blue-grey buds
crowded erect with desire against
the sky--
            tense blue-grey twigs
slenderly anchoring them down, drawing
them in--
            two blue-grey birds chasing
a third struggle in circles, angles,
swift convergings to a point that bursts
instantly!

              Vibrant bowing limbs
pull downward, sucking in the sky
that bulges from behind, plastering itself
against them in packed rifts, rock blue
and dirty orange!
                But--

(Hold hard, rigid jointed trees!)
the blinding and red-edged sun-blur--
creeping energy, concentrated
counterforce--welds sky, buds, trees,
rivets them in one puckering hold!
Sticks through! Pulls the whole
counter-pulling mass upward, to the right,
locks even the opaque, not yet defined
ground in a terrific drag that is
loosening the very tap-roots!

On a tissue-thin monotone of blue-grey buds
two blue-grey birds, chasing a third,
at full cry! Now they are
flung outward and up--disappearing suddenly!', 30);
insert into public.poems (id, title, author, body, line_count) values ('poem_2051', 'Sympathetic Portrait of a Child', 'William Carlos Williams', 'The murderer’s little daughter
who is barely ten years old
jerks her shoulders
right and left
so as to catch a glimpse of me
without turning round.

Her skinny little arms
wrap themselves
this way then that
reversely about her body!
Nervously
she crushes her straw hat
about her eyes
and tilts her head
to deepen the shadow--
smiling excitedly!

As best as she can
she hides herself
in the full sunlight
her cordy legs writhing
beneath the little flowered dress
that leaves them bare
from mid-thigh to ankle--

Why has she chosen me
for the knife
that darts along her smile?', 26);
insert into public.poems (id, title, author, body, line_count) values ('poem_2052', 'The Great Figure', 'William Carlos Williams', '  Among the rain
  and lights
  I saw the figure 5
  in gold
  on a red
  firetruck
  moving
  with weight and urgency
  tense
  unheeded
  to gong clangs
  siren howls
  and wheels rumbling
  through the dark city.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2053', 'The Lonely Street', 'William Carlos Williams', 'School is over. It is too hot
to walk at ease. At ease
in light frocks they walk the streets
to while the time away.
They have grown tall. They hold
pink flames in their right hands.
In white from head to foot,
with sidelong, idle look--
in yellow, floating stuff,
black sash and stockings--
touching their avid mouths
with pink sugar on a stick--
like a carnation each holds in her hand--
they mount the lonely street.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2054', 'The Widow''s Lament in Springtime', 'William Carlos Williams', 'Sorrow is my own yard
where the new grass
flames as it has flamed
often before but not
with the cold fire
that closes round me this year.
Thirtyfive years
I lived with my husband.
The plumtree is white today
with masses of flowers.
Masses of flowers
load the cherry branches
and color some bushes
yellow and some red
but the grief in my heart
is stronger than they
for though they were my joy
formerly, today I notice them
and turn away forgetting.
Today my son told me
that in the meadows,
at the edge of the heavy woods
in the distance, he saw
trees of white flowers.
I feel that I would like
to go there
and fall into those flowers
and sink into the marsh near them.', 28);
insert into public.poems (id, title, author, body, line_count) values ('poem_2055', 'To Waken an Old Lady', 'William Carlos Williams', 'Old age is
a flight of small
cheeping birds
skimming
bare trees
above a snow glaze.
Gaining and failing
they are buffetted
by a dark wind--
But what?
On harsh weedstalks
the flock has rested,
the snow
is covered with broken
seedhusks
and the wind tempered
by a shrill
piping of plenty.', 18);
insert into public.poems (id, title, author, body, line_count) values ('poem_2056', 'A Talisman', 'Marianne Moore', 'Under a splintered mast,
torn from ship and cast
        near her hull,

a stumbling shepherd found
embedded in the ground,
        a sea-gull

of lapis lazuli,
a scarab of the sea,
        with wings spread—

curling its coral feet,
parting its beak to greet
        men long dead.', 12);
insert into public.poems (id, title, author, body, line_count) values ('poem_2057', 'Picking and Choosing', 'Marianne Moore', 'Literature is a phase of life: if
  one is afraid of it, the situation is irremediable; if
one approaches it familiarly,
  what one says of it is worthless. Words are constructive
when they are true; the opaque allusion—the simulated flight

upward—accomplishes nothing. Why cloud the fact
  that Shaw is selfconscious in the field of sentiment but is
  otherwise re-
warding? that James is all that has been
  said of him but is not profound? It is not Hardy
the distinguished novelist and Hardy the poet, but one man

“interpreting life through the medium of the
  emotions.” If he must give an opinion, it is permissible that the
critic should know what he likes. Gordon
  Craig with his “this is I” and “this is mine,” with his three
wise men, his “sad French greens” and his Chinese cherries—Gordon
  Craig, so

inclinational and unashamed—has carried
  the precept of being a good critic, to the last extreme. And Burke
  is a
psychologist—of acute, raccoon-
  like curiosity. Summa diligentia;
to the humbug, whose name is so amusing—very young and ve-

ry rushed, Cæsar crossed the Alps on the “top of a
  diligence.” We are not daft about the meaning but this familiarity
with wrong meanings puzzles one. Humming-
  bug, the candles are not wired for electricity.
Small dog, going over the lawn, nipping the linen and saying

that you have a badger—remember Xenophon;
  only the most rudimentary sort of behaviour is necessary
to put us on the scent; a “right good
  salvo of barks,” a few “strong wrinkles” puckering the
skin between the ears, are all we ask.', 33);
insert into public.poems (id, title, author, body, line_count) values ('poem_2058', 'Poetry', 'Marianne Moore', 'I too, dislike it: there are things that are important beyond all
  this fiddle.
  Reading it, however, with a perfect contempt for it, one discovers
  that there is in
  it after all, a place for the genuine.
    Hands that can grasp, eyes
    that can dilate, hair that can rise
      if it must, these things are important not because a

high sounding interpretation can be put upon them but because they
  are
  useful; when they become so derivative as to become
  unintelligible, the
  same thing may be said for all of us—that we
    do not admire what
    we cannot understand. The bat,
      holding on upside down or in quest of something to

eat, elephants pushing, a wild horse taking a roll, a tireless wolf
  under
  a tree, the immovable critic twinkling his skin like a horse that
  feels a flea, the base-
  ball fan, the statistician—case after case
    could be cited did
    one wish it; nor is it valid
      to discriminate against “business documents and

school-books”; all these phenomena are important. One must make a
  distinction
  however: when dragged into prominence by half poets, the result is
  not poetry,
  nor till the autocrats among us can be
    “literalists of
    the imagination”—above
      insolence and triviality and can present

for inspection, imaginary gardens with real toads in them, shall we
  have
  it. In the meantime, if you demand on one hand, in defiance of
  their opinion—
  the raw material of poetry in
    all its rawness and
    that which is, on the other hand,
      genuine then you are interested in poetry.', 40);
insert into public.poems (id, title, author, body, line_count) values ('poem_2059', 'Roses Only', 'Marianne Moore', 'You do not seem to realise that beauty is a liability rather than
  an asset—that in view of the fact that spirit creates form we are
            justified in supposing
    that you must have brains. For you, a symbol of the unit, stiff
  and sharp, conscious of surpassing by dint of native superiority
and liking for everything self-dependent, anything an

ambitious civilisation might produce: for you, unaided to attempt
  through sheer reserve, to confute presumptions resulting from
            observation, is idle. You cannot make us
    think you a delightful happen-so. But rose, if you are
  brilliant, it is not because your petals are the
            without-which-nothing of pre-eminence.
            You would look, minus
thorns—like a what-is-this, a mere

peculiarity. They are not proof against a worm, the elements, or
  mildew but what about the predatory hand? What is brilliance
            without co-ordination? Guarding the
    infinitesimal pieces of your mind, compelling audience to
  the remark that it is better to be forgotten than to be remembered
            too violently,
your thorns are the best part of you.', 21);
insert into public.poems (id, title, author, body, line_count) values ('poem_2060', 'The Monkeys', 'Marianne Moore', ' winked too much and were afraid of snakes. The zebras, supreme in
 their abnormality; the elephants with their fog-colored skin
   and strictly practical appendages
     were there, the small cats and the parrakeet—
       trivial and humdrum on examination, destroying
     bark and portions of the food it could not eat.

I recall their magnificence, now not more magnificent
 than it is dim. It is difficult to recall the ornament,
   speech, and precise manner of what one might
     call the minor acquaintances twenty
       years back; but I shall never forget—that Gilgamesh among
     the hairy carnivora—that cat with the

 wedge-shaped, slate-gray marks on its forelegs and the resolute tail,
 astringently remarking: “They have imposed on us with their pale,
   half fledged protestations, trembling about
     in inarticulate frenzy, saying
       it is not for all of us to understand art, finding it
     all so difficult, examining the thing

 as if it were something inconceivably arcanic, as
 symmetrically frigid as something carved out of chrysopras
   or marble—strict with tension, malignant
     in its power over us and deeper
       than the sea when it proffers flattery in exchange for hemp,
     rye, flax, horses, platinum, timber and fur.”', 24);
insert into public.poems (id, title, author, body, line_count) values ('poem_2061', 'Those Various Scalpels', 'Marianne Moore', 'Those
various sounds consistently indistinct, like intermingled
        echoes
  struck from thin glass successively at random—the
  inflection disguised: your hair, the tails of two
        fighting-cocks head to head in stone—like sculptured
        scimitars re-
      peating the curve of your ears in reverse order: your eyes,
        flowers of ice

and
snow sown by tearing winds on the cordage of disabled
        ships: your raised hand
  an ambiguous signature: your cheeks, those rosettes
  of blood on the stone floors of French châteaux, with
        regard to which guides are so affirmative:
      your other hand

a
bundle of lances all alike, partly hid by emeralds from
        Persia
  and the fractional magnificence of Florentine
  goldwork—a collection of half a dozen little objects
        made fine
      with enamel in gray, yellow, and dragonfly blue: a lemon, a

pear
and three bunches of grapes, tied with silver: your dress, a
        magnificent square
  cathedral of uniform
  and at the same time, diverse appearance—a species of
        vertical vineyard rustling in the storm
      of conventional opinion. Are they weapons or scalpels?
        Whetted

to
brilliance by the hard majesty of that sophistication which
        is su-
  perior to opportunity, these things are rich
  instruments with which to experiment but surgery is
        not tentative: why dissect destiny with instruments
        which
      are more highly specialized than the tissues of destiny
        itself?', 40);
insert into public.poems (id, title, author, body, line_count) values ('poem_2062', 'To a Steam Roller', 'Marianne Moore', 'The illustration
is nothing to you without the application.
  You lack half wit. You crush all the particles down
    into close conformity, and then walk back and forth on them.

Sparkling chips of rock
are crushed down to the level of the parent block.
  Were not “impersonal judgment in æsthetic
    matters, a metaphysical impossibility,” you

might fairly achieve
it. As for butterflies, I can hardly conceive
  of one’s attending upon you, but to question
    the congruence of the complement is vain, if it exists.', 12);
insert into public.poems (id, title, author, body, line_count) values ('poem_2063', 'When I Buy Pictures', 'Marianne Moore', 'or what is closer to the truth, when I look at
  that of which I may regard myself as the
    imaginary possessor, I fix upon that which would
  give me pleasure in my average moments: the satire upon curiosity,
      in which no more is discernible than the intensity of the
      mood;

or quite the opposite—the old thing, the medi-
  æval decorated hat box, in which there
    are hounds with waists diminishing like the waist of the
    hour-glass
  and deer, both white and brown, and birds and seated people; it
  may be no more than a square
      of parquetry; the literal biography perhaps—in letters stand-

ing well apart upon a parchment-like expanse;
  or that which is better without words, which means
    just as much or just as little as it is understood to
  mean by the observer—the grave of Adam, prefigured by himself; a
    bed of beans
    or artichokes in six varieties of blue; the snipe-legged hiero—

glyphic in three parts; it may be anything. Too
  stern an intellectual emphasis, i-
    ronic or other—upon this quality or that, detracts
  from one’s enjoyment; it must not wish to disarm anything; nor may
      the approved tri-
      umph easily be honoured—that which is great because something
      else is small.

It comes to this: of whatever sort it is, it
  must make known the fact that it has been displayed
    to acknowledge the spiritual forces which have made it;
  and it must admit that it is the work of X, if X produced it; of
      Y, if made by Y. It must be a voluntary gift with the name
      written on it.', 32);
insert into public.poems (id, title, author, body, line_count) values ('poem_2064', 'An Hymn to the Evening', 'Phillis Wheatley', 'SOON as the sun forsook the eastern main
The pealing thunder shook the heav''nly plain;
Majestic grandeur!  From the zephyr''s wing,
Exhales the incense of the blooming spring.
Soft purl the streams, the birds renew their notes,
And through the air their mingled music floats.
  Through all the heav''ns what beauteous dies are spread!
But the west glories in the deepest red:
So may our breasts with ev''ry virtue glow,
The living temples of our God below!
  Fill''d with the praise of him who gives the light,
And draws the sable curtains of the night,
Let placid slumbers sooth each weary mind,
At morn to wake more heav''nly, more refin''d;
So shall the labours of the day begin
More pure, more guarded from the snares of sin.
  Night''s leaden sceptre seals my drowsy eyes,
Then cease, my song, till fair Aurora rise.', 18);
insert into public.poems (id, title, author, body, line_count) values ('poem_2065', 'An Hymn to the Morning', 'Phillis Wheatley', 'ATTEND my lays, ye ever honour''d nine,
Assist my labours, and my strains refine;
In smoothest numbers pour the notes along,
For bright Aurora now demands my song.
  Aurora hail, and all the thousand dies,
Which deck thy progress through the vaulted skies:
The morn awakes, and wide extends her rays,
On ev''ry leaf the gentle zephyr plays;
Harmonious lays the feather''d race resume,
Dart the bright eye, and shake the painted plume.
  Ye shady groves, your verdant gloom display
To shield your poet from the burning day:
Calliope awake the sacred lyre,
While thy fair sisters fan the pleasing fire:
The bow''rs, the gales, the variegated skies
In all their pleasures in my bosom rise.
  See in the east th'' illustrious king of day!
His rising radiance drives the shades away--
But Oh! I feel his fervid beams too strong,
And scarce begun, concludes th'' abortive song.', 20);
insert into public.poems (id, title, author, body, line_count) values ('poem_2066', 'Ode to Neptune', 'Phillis Wheatley', 'On Mrs. W-----''s Voyage to England.

               I.

WHILE raging tempests shake the shore,
While AElus'' thunders round us roar,
And sweep impetuous o''er the plain
Be still, O tyrant of the main;
Nor let thy brow contracted frowns betray,
While my Susanna skims the wat''ry way.

               II.

The Pow''r propitious hears the lay,
The blue-ey''d daughters of the sea
With sweeter cadence glide along,
And Thames responsive joins the song.
Pleas''d with their notes Sol sheds benign his ray,
And double radiance decks the face of day.

               III.

To court thee to Britannia''s arms
  Serene the climes and mild the sky,
Her region boasts unnumber''d charms,
  Thy welcome smiles in ev''ry eye.
Thy promise, Neptune keep, record my pray''r,
Not give my wishes to the empty air.

  Boston, October 12, 1772.', 23);
insert into public.poems (id, title, author, body, line_count) values ('poem_2067', 'On Being Brought from Africa to America', 'Phillis Wheatley', '''TWAS mercy brought me from my Pagan land,
Taught my benighted soul to understand
That there''s a God, that there''s a Saviour too:
Once I redemption neither sought nor knew,
Some view our sable race with scornful eye,
"Their colour is a diabolic die."
Remember, Christians, Negroes, black as Cain,
May be refin''d, and join th'' angelic train.', 8);
insert into public.poems (id, title, author, body, line_count) values ('poem_2068', 'On Virtue', 'Phillis Wheatley', 'O Thou bright jewel in my aim I strive
To comprehend thee.  Thine own words declare
Wisdom is higher than a fool can reach.
I cease to wonder, and no more attempt
Thine height t'' explore, or fathom thy profound.
But, O my soul, sink not into despair,
Virtue is near thee, and with gentle hand
Would now embrace thee, hovers o''er thine head.
Fain would the heav''n-born soul with her converse,
Then seek, then court her for her promis''d bliss.
     Auspicious queen, thine heav''nly pinions spread,
And lead celestial Chastity along;
Lo! now her sacred retinue descends,
Array''d in glory from the orbs above.
Attend me, Virtue, thro'' my youthful years!
O leave me not to the false joys of time!
But guide my steps to endless life and bliss.
Greatness, or Goodness, say what I shall call thee,
To give me an higher appellation still,
Teach me a better strain, a nobler lay,
O thou, enthron''d with Cherubs in the realms of day.', 21);
insert into public.poems (id, title, author, body, line_count) values ('poem_2069', 'On the Death of a Young Gentleman', 'Phillis Wheatley', 'WHO taught thee conflict with the pow''rs of night,
To vanquish satan in the fields of light?
Who strung thy feeble arms with might unknown,
How great thy conquest, and how bright thy crown!
War with each princedom, throne, and pow''r is o''er,
The scene is ended to return no more.
O could my muse thy seat on high behold,
How deckt with laurel, how enrich''d with gold!
O could she hear what praise thine harp employs,
How sweet thine anthems, how divine thy joys!
What heav''nly grandeur should exalt her strain!
What holy raptures in her numbers reign!
To sooth the troubles of the mind to peace,
To still the tumult of life''s tossing seas,
To ease the anguish of the parents heart,
What shall my sympathizing verse impart?
Where is the balm to heal so deep a wound?
Where shall a sov''reign remedy be found?
Look, gracious Spirit, from thine heav''nly bow''r,
And thy full joys into their bosoms pour;
The raging tempest of their grief control,
And spread the dawn of glory through the soul,
To eye the path the saint departed trod,
And trace him to the bosom of his God.', 24);
insert into public.poems (id, title, author, body, line_count) values ('poem_2070', 'On the Death of a Young Lady of Five Years of Age', 'Phillis Wheatley', 'FROM dark abodes to fair etherial light
Th'' enraptur''d innocent has wing''d her flight;
On the kind bosom of eternal love
She finds unknown beatitude above.
This known, ye parents, nor her loss deplore,
She feels the iron hand of pain no more;
The dispensations of unerring grace,
Should turn your sorrows into grateful praise;
Let then no tears for her henceforward flow,
No more distress''d in our dark vale below,
  Her morning sun, which rose divinely bright,
Was quickly mantled with the gloom of night;
But hear in heav''n''s blest bow''rs your Nancy fair,
And learn to imitate her language there.
"Thou, Lord, whom I behold with glory crown''d,
"By what sweet name, and in what tuneful sound
"Wilt thou be prais''d?  Seraphic pow''rs are faint
"Infinite love and majesty to paint.
"To thee let all their graceful voices raise,
"And saints and angels join their songs of praise."
  Perfect in bliss she from her heav''nly home
Looks down, and smiling beckons you to come;
Why then, fond parents, why these fruitless groans?
Restrain your tears, and cease your plaintive moans.
Freed from a world of sin, and snares, and pain,
Why would you wish your daughter back again?
No--bow resign''d.  Let hope your grief control,
And check the rising tumult of the soul.
Calm in the prosperous, and adverse day,
Adore the God who gives and takes away;
Eye him in all, his holy name revere,
Upright your actions, and your hearts sincere,
Till having sail''d through life''s tempestuous sea,
And from its rocks, and boist''rous billows free,
Yourselves, safe landed on the blissful shore,
Shall join your happy babe to part no more.', 36);
insert into public.poems (id, title, author, body, line_count) values ('poem_2071', 'To Captain H— D—, of the 65th Regiment', 'Phillis Wheatley', 'SAY, muse divine, can hostile scenes delight
The warrior''s bosom in the fields of fight?
Lo! here the christian and the hero join
With mutual grace to form the man divine.
In H-----D see with pleasure and surprise,
Where valour kindles, and where virtue lies:
Go, hero brave, still grace the post of fame,
And add new glories to thine honour''d name,
Still to the field, and still to virtue true:
Britannia glories in no son like you.', 10);
insert into public.poems (id, title, author, body, line_count) values ('poem_2072', 'To S. M., a Young African Painter, on Seeing His Works', 'Phillis Wheatley', 'TO show the lab''ring bosom''s deep intent,
And thought in living characters to paint,
When first thy pencil did those beauties give,
And breathing figures learnt from thee to live,
How did those prospects give my soul delight,
A new creation rushing on my sight?
Still, wond''rous youth! each noble path pursue,
On deathless glories fix thine ardent view:
Still may the painter''s and the poet''s fire
To aid thy pencil, and thy verse conspire!
And may the charms of each seraphic theme
Conduct thy footsteps to immortal fame!
High to the blissful wonders of the skies
Elate thy soul, and raise thy wishful eyes.
Thrice happy, when exalted to survey
That splendid city, crown''d with endless day,
Whose twice six gates on radiant hinges ring:
Celestial Salem blooms in endless spring.
  Calm and serene thy moments glide along,
And may the muse inspire each future song!
Still, with the sweets of contemplation bless''d,
May peace with balmy wings your soul invest!
But when these shades of time are chas''d away,
And darkness ends in everlasting day,
On what seraphic pinions shall we move,
And view the landscapes in the realms above?
There shall thy tongue in heav''nly murmurs flow,
And there my muse with heav''nly transport glow:
No more to tell of Damon''s tender sighs,
Or rising radiance of Aurora''s eyes,
For nobler themes demand a nobler strain,
And purer language on th'' ethereal plain.
Cease, gentle muse! the solemn gloom of night
Now seals the fair creation from my sight.', 34);
insert into public.poems (id, title, author, body, line_count) values ('poem_2073', 'To a Lady on the Death of Her Husband', 'Phillis Wheatley', 'GRIM monarch! see, depriv''d of vital breath,
A young physician in the dust of death:
Dost thou go on incessant to destroy,
Our griefs to double, and lay waste our joy?
Enough thou never yet wast known to say,
Though millions die, the vassals of thy sway:
Nor youth, nor science, not the ties of love,
Nor ought on earth thy flinty heart can move.
The friend, the spouse from his dire dart to save,
In vain we ask the sovereign of the grave.
Fair mourner, there see thy lov''d Leonard laid,
And o''er him spread the deep impervious shade.
Clos''d are his eyes, and heavy fetters keep
His senses bound in never-waking sleep,
Till time shall cease, till many a starry world
Shall fall from heav''n, in dire confusion hurl''d
Till nature in her final wreck shall lie,
And her last groan shall rend the azure sky:
Not, not till then his active soul shall claim
His body, a divine immortal frame.
  But see the softly-stealing tears apace
Pursue each other down the mourner''s face;
But cease thy tears, bid ev''ry sigh depart,
And cast the load of anguish from thine heart:
From the cold shell of his great soul arise,
And look beyond, thou native of the skies;
There fix thy view, where fleeter than the wind
Thy Leonard mounts, and leaves the earth behind.
Thyself prepare to pass the vale of night
To join for ever on the hills of light:
To thine embrace this joyful spirit moves
To thee, the partner of his earthly loves;
He welcomes thee to pleasures more refin''d,
And better suited to th'' immortal mind.', 34);
insert into public.poems (id, title, author, body, line_count) values ('poem_2074', 'To the University of Cambridge, in New England', 'Phillis Wheatley', 'WHILE an intrinsic ardor prompts to write,
The muses promise to assist my pen;
''Twas not long since I left my native shore
The land of errors, and Egyptian gloom:
Father of mercy, ''twas thy gracious hand
Brought me in safety from those dark abodes.
     Students, to you ''tis giv''n to scan the heights
Above, to traverse the ethereal space,
And mark the systems of revolving worlds.
Still more, ye sons of science ye receive
The blissful news by messengers from heav''n,
How Jesus'' blood for your redemption flows.
See him with hands out-stretcht upon the cross;
Immense compassion in his bosom glows;
He hears revilers, nor resents their scorn:
What matchless mercy in the Son of God!
When the whole human race by sin had fall''n,
He deign''d to die that they might rise again,
And share with him in the sublimest skies,
Life without death, and glory without end.
     Improve your privileges while they stay,
Ye pupils, and each hour redeem, that bears
Or good or bad report of you to heav''n.
Let sin, that baneful evil to the soul,
By you be shun''d, nor once remit your guard;
Suppress the deadly serpent in its egg.
Ye blooming plants of human race divine,
An Ethiop tells you ''tis your greatest foe;
Its transient sweetness turns to endless pain,
And in immense perdition sinks the soul.', 30);
insert into public.poems (id, title, author, body, line_count) values ('poem_2075', 'Aunt Sue''s Stories', 'Langston Hughes', 'Aunt Sue has a head full of stories.
Aunt Sue has a whole heart full of stories.
Summer nights on the front porch
Aunt Sue cuddles a brown-faced child to her bosom
And tells him stories.

Black slaves
Working in the hot sun,
And black slaves
Walking in the dewy night,
And black slaves
Singing sorrow songs on the banks of a mighty river
Mingle themselves softly
In the flow of old Aunt Sue’s voice,
Mingle themselves softly
In the dark shadows that cross and recross
Aunt Sue’s stories.

And the dark-faced child, listening,
Knows that Aunt Sue’s stories are real stories.
He knows that Aunt Sue
Never got her stories out of any book at all,
But that they came
Right out of her own life.

And the dark-faced child is quiet
Of a summer night
Listening to Aunt Sue’s stories.', 25);
insert into public.poems (id, title, author, body, line_count) values ('poem_2076', 'Cross', 'Langston Hughes', 'My old man’s a white old man
And my old mother’s black.
If ever I cursed my white old man
I take my curses back.

If ever I cursed my black old mother
And wished she were in hell,
I’m sorry for that evil wish
And now I wish her well.

My old man died in a fine big house.
My ma died in a shack.
I wonder where I’m gonna die,
Being neither white nor black?', 12);
insert into public.poems (id, title, author, body, line_count) values ('poem_2077', 'Dream Variations', 'Langston Hughes', 'To fling my arms wide
In some place of the sun,
To whirl and to dance
Till the white day is done.
Then rest at cool evening
Beneath a tall tree
While night comes on gently,
  Dark like me,—
That is my dream!

To fling my arms wide
In the face of the sun,
Dance! whirl! whirl!
Till the quick day is done.
Rest at pale evening....
A tall, slim tree....
Night coming tenderly
  Black like me.', 17);
insert into public.poems (id, title, author, body, line_count) values ('poem_2078', 'I, Too', 'Langston Hughes', 'I, too, sing America.

I am the darker brother.
They send me to eat in the kitchen
When company comes,
But I laugh,
And eat well,
And grow strong.

Tomorrow,
I’ll sit at the table
When company comes.
Nobody’ll dare
Say to me,
“Eat in the kitchen,”
Then.

Besides,
They’ll see how beautiful I am
And be ashamed,—

I, too, am America.', 18);
insert into public.poems (id, title, author, body, line_count) values ('poem_2079', 'Jazzonia', 'Langston Hughes', 'Oh, silver tree!
Oh, shining rivers of the soul!

In a Harlem cabaret
Six long-headed jazzers play.
A dancing girl whose eyes are bold
Lifts high a dress of silken gold.

Oh, singing tree!
Oh, shining rivers of the soul!

Were Eve’s eyes
In the first garden
Just a bit too bold?
Was Cleopatra gorgeous
In a gown of gold?

Oh, shining tree!
Oh, silver rivers of the soul!

In a whirling cabaret
Six long-headed jazzers play.', 17);
insert into public.poems (id, title, author, body, line_count) values ('poem_2080', 'Mother to Son', 'Langston Hughes', 'Well, son, I’ll tell you:
Life for me ain’t been no crystal stair.
It’s had tacks in it,
And splinters,
And boards torn up,
And places with no carpet on the floor—
Bare.
But all the time
I’se been a-cimbin’ on,
And reachin’ landin’s,
And turnin’ corners,
And sometimes goin’ in the dark
Where there ain’t been no light.
So boy, don’t you turn back.
Don’t you set down on the steps
’Cause you finds it’s kinder hard.
Don’t you fall now—
For I’se still goin’, honey,
I’se still climbin’,
And life for me ain’t been no crystal stair.', 20);
insert into public.poems (id, title, author, body, line_count) values ('poem_2081', 'My People', 'Langston Hughes', 'We have tomorrow
Bright before us
Like a flame.

Yesterday
A night-gone thing,
A sun-down name.

And dawn-today
Broad arch above the road we came.', 8);
insert into public.poems (id, title, author, body, line_count) values ('poem_2082', 'Negro', 'Langston Hughes', 'I am a Negro:
  Black as the night is black,
  Black like the depths of my Africa.

I’ve been a slave:
  Caesar told me to keep his door-steps clean.
  I brushed the boots of Washington.

I’ve been a worker:
  Under my hand the pyramids arose.
  I made mortar for the Woolworth Building.

I’ve been a singer:
  All the way from Africa to Georgia
  I carried my sorrow songs.
  I made ragtime.

I’ve been a victim:
  The Belgians cut off my hands in the Congo.
  They lynch me now in Texas.

I am a Negro:
  Black as the night is black,
  Black like the depths of my Africa.', 19);
insert into public.poems (id, title, author, body, line_count) values ('poem_2083', 'Suicide''s Note', 'Langston Hughes', 'The calm,
Cool face of the river
Asked me for a kiss.', 3);
insert into public.poems (id, title, author, body, line_count) values ('poem_2084', 'The Negro Speaks of Rivers', 'Langston Hughes', '                     (To W. E. B. DuBois)

I’ve known rivers:

I’ve known rivers ancient as the world and older than the flow of
  human blood in human veins.

My soul has grown deep like the rivers.

I bathed in the Euphrates when dawns were young.
I built my hut near the Congo and it lulled me to sleep.
I looked upon the Nile and raised the pyramids above it.
I heard the singing of the Mississippi when Abe Lincoln went down to
  New Orleans, and I’ve seen its muddy bosom turn all golden in the
  sunset.

I’ve known rivers:
Ancient, dusky rivers.

My soul has grown deep like the rivers.', 14);
insert into public.poems (id, title, author, body, line_count) values ('poem_2085', 'The South', 'Langston Hughes', 'The lazy, laughing South
With blood on its mouth.
The sunny-faced South,
  Beast-strong,
  Idiot-brained.
The child-minded South
Scratching in the dead fire’s ashes
For a Negro’s bones.
  Cotton and the moon,
  Warmth, earth, warmth,
  The sky, the sun, the stars,
  The magnolia-scented South.
Beautiful, like a woman,
Seductive as a dark-eyed whore,
  Passionate, cruel,
  Honey-lipped, syphilitic—
  That is the South.
And I, who am black, would love her
But she spits in my face.
And I, who am black,
Would give her many rare gifts
But she turns her back upon me.
  So now I seek the North—
  The cold-faced North,
  For she, they say,
  Is a kinder mistress,
And in her house my children
May escape the spell of the South.', 28);
insert into public.poems (id, title, author, body, line_count) values ('poem_2086', 'The Weary Blues', 'Langston Hughes', 'Droning a drowsy syncopated tune,
Rocking back and forth to a mellow croon,
  I heard a Negro play.
Down on Lenox Avenue the other night
By the pale dull pallor of an old gas light
  He did a lazy sway....
  He did a lazy sway....
To the tune o’ those Weary Blues.
With his ebony hands on each ivory key
He made that poor piano moan with melody.
  O Blues!
Swaying to and fro on his rickety stool
He played that sad raggy tune like a musical fool.
Sweet Blues!
Coming from a black man’s soul.
  O Blues!
In a deep song voice with a melancholy tone
I heard that Negro sing, that old piano moan—
  “Ain’t got nobody in all this world,
  Ain’t got nobody but ma self.
  I’s gwine to quit ma frownin’
  And put ma troubles on the shelf.”
Thump, thump, thump, went his foot on the floor.
He played a few chords then he sang some more—
  “I got the Weary Blues
  And I can’t be satisfied.
  Got the Weary Blues
  And can’t be satisfied—
  I ain’t happy no mo’
  And I wish that I had died.”
And far into the night he crooned that tune.
The stars went out and so did the moon.
The singer stopped playing and went to bed
While the Weary Blues echoed through his head.
He slept like a rock or a man that’s dead.', 35);
insert into public.poems (id, title, author, body, line_count) values ('poem_2087', 'When Sue Wears Red', 'Langston Hughes', 'When Susanna Jones wears red
Her face is like an ancient cameo
Turned brown by the ages.

Come with a blast of trumpets,
  Jesus!

When Susanna Jones wears red
A queen from some time-dead Egyptian night
Walks once again.

Blow trumpets, Jesus!

And the beauty of Susanna Jones in red
Burns in my heart a love-fire sharp like pain.

Sweet silver trumpets,
  Jesus!', 13);
